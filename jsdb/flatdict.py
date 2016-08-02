"""A dictionary that flattens a nested key-value mappings and lists into a store that does not support nesting.
"""

import collections
import itertools
import logging
import types
import unittest

from . import python_copy
from .flatpath import FlatPath
from . import flatpath

LOGGER = logging.getLogger('jsdb.flatdict')

ASCII_TOP = '\xff'

class JsonFlatteningDict(collections.MutableMapping):
    "Flatten nested list and dictionaries down to a string to value mapping"

    # The format of the keys is
    #   path := dot (dict_key (path | equals))? | bracket (list_index (path | equals))?
    #   list_index := integer right_bracket
    #   dict_key := " dict_key_string "
    #   `equals` is the string "="
    #   `bracket` is the string "["
    #   `dict_key_string` python escape string

    # Example

    # ."hello"[0]."world"=
    #     stores the value of d["hello"][0]["world"]

    # ."hello".
    #      indicates that d["hello"] is a dictionary (possibly empty)

    # ."hello"[
    #       indicates that d["hello"] is a list (possibly empty)

    # We must enforce things like:
    #   not having more than precisely value, list, or dictionary path for the same prefix

    def __repr__(self):
        return '<JsonFlatteningDict path={!r}>'.format(self._prefix)

    def __init__(self, underlying, prefix=''):
        self._prefix = prefix
        self._path = FlatPath(prefix)
        self._underlying = underlying
        self._flat_store = FlatteningStore(self._underlying)

    def __getitem__(self, key):
        if not isinstance(key, str):
            raise ValueError(key)

        item_prefix = self._path.dict().lookup(key).key()
        return self._flat_store.lookup(item_prefix)

    def __len__(self):
        index = -1
        for index, _ in enumerate(self):
            pass
        return index + 1

    def __iter__(self):
        key_after = key_after_func(self._underlying)
        if key_after:
            return self._key_after_iter(key_after)
        else:
            return self._bad_depth_scaling_iter()

    def _bad_depth_scaling_iter(self):
        # If we can't do ordering based queries on keys
        #  then iteration is O(total nodes)
        for k in self._underlying:
            if self._is_child_key(k):
                child_path = FlatPath(k)
                yield child_path.prefix().key_string()

    def _is_child_key(self, key):
        child_path = FlatPath(key)
        return child_path.prefix().parent().key() == self._prefix

    def _key_after_iter(self, key_after):
        # If we can do ordering-based lookups (and hence
        #   prefix-based) queries efficiently then
        #   iter becomes a lot more efficient

        # Commence literate programming! (Too complicated to
        #   be understood with code alone)

        # We start with something like "a"
        #     We want to find something like "a"."b"
        #     but not "a".

        # So we search for things after "a".
        #   the result found is guaranteed to be a child
        #   because "a"."b". and "a"."b"[ precede
        #   their descendants
        try:
            child_path = FlatPath(key_after(self._underlying, self._path.dict().key()))
        except KeyError:
            return

        while True:
            if not child_path.key().startswith(self._path.dict().key()):
                break
            yield child_path.prefix().key_string()

            # We have something like "a"."b". or "a"."b"[ or "a"."b"=
            # We want to skip over all the children
            #   so we want to look for "a"."b".TOP "a"."b"[TOP or "a"."b"=
            try:
                #  this is a child because the type string always precedes it's children
                child_key = key_after(self._underlying, child_path.key() + ASCII_TOP)
                child_path = FlatPath(child_key)
            except KeyError:
                break

    def __delitem__(self, key):
        self._flat_store.purge_prefix(self._path.dict().lookup(key).key())

    def __setitem__(self, key, value):
        #LOGGER.debug('%r: Setting %r -> %r', self, key, value)
        if not isinstance(key, str):
            raise ValueError(key)

        self.pop(key, None)
        if isinstance(value, (int, str, float, types.NoneType, bool)):
            flat_key = self._path.dict().lookup(key).value().key()
            self._underlying[flat_key] = value
        elif isinstance(value, dict):
            base_path = self._path.dict().lookup(key)
            self._underlying[base_path.dict().key()] = True
            dict_store = self[key]
            for dict_key in value:
                dict_store[dict_key] = value[dict_key]
        elif isinstance(value, list):
            base_path = self._path.dict().lookup(key)
            self._underlying[base_path.list().key()] = True

            list_store = self[key]
            for item in value:
                list_store.append(item)
        else:
            raise ValueError(value)


def key_after_func(store):
    if isinstance(store, FakeOrderedDict):
        return FakeOrderedDict.key_after
    else:
        return None

class JsonFlatteningList(collections.MutableSequence):
    def __init__(self, underlying, prefix):
        self._prefix = prefix
        self._underlying = underlying
        self._flat_store = FlatteningStore(self._underlying)
        self._path = FlatPath(prefix)

    def __getitem__(self, index):
        index = self._simplify_index(index)
        return self._getitem(index)

    def __len__(self):
        for i in itertools.count(0):
            try:
                self._getitem(i)
            except IndexError:
                return i

    def _simplify_index(self, index):
        length = len(self)
        if -length <= index < 0:
            return len(self) + index
        elif index < len(self):
            return index
        else:
            raise IndexError(index)

    def _getitem(self, index):
        item_prefix = self._path.list().index(index)
        try:
            return self._flat_store.lookup(item_prefix.key())
        except KeyError:
            raise IndexError(index)

    def __setitem__(self, index, value):
        self._set_item(index, value)

    def _set_item(self, index, value, check_index=True):
        if check_index:
            if not 0 <= index < len(self):
                raise IndexError('assignment out of range')

        self._flat_store.purge_prefix(self._path.list().index(index).key())

        if isinstance(value, (int, str, float, types.NoneType, bool)):
            self._underlying[self._path.list().index(index).value().key()] = value
        elif isinstance(value, (dict, JsonFlatteningDict)):
            dict_key = self._path.list().index(index)
            self._underlying[dict_key.dict().key()] = True
            nested_dict = self[index]
            for key, nested_value in value.items():
                nested_dict[key] = nested_value
        elif isinstance(value, (list, JsonFlatteningList)):
            list_key = self._path.list().index(index)
            self._underlying[list_key.list().key()] = True
            nested_list = self[index]
            for nested_value in value:
                nested_list.append(nested_value)
        else:
            raise ValueError(value)

    def __delitem__(self, index):
        index = self._simplify_index(index)

        length = len(self)

        if not 0 <= index < length:
            raise IndexError(index)

        for i in range(length - 1):
            if i < index:
                continue
            else:
                self[i] = self[i + 1]
        self._flat_store.purge_prefix(self._path.list().index(length - 1).key())

    def insert(self, pos, value):
        # We need to do our own value shifting
        inserted_value = value
        length = len(self)
        for i in range(length):
            if i < pos:
                continue
            else:
                self[i], inserted_value = inserted_value, self[i]
        self._set_item(length, inserted_value, check_index=False)


class FlatteningStore(object):
    def __init__(self, underlying):
        self._underlying = underlying

    def lookup(self, item_prefix):
        "Lookup a value in the json flattening store underlying"

        item_path = FlatPath(item_prefix)

        has_terminal_key = self._has_terminal_key(item_prefix)
        has_dict_key = self._has_dict_key(item_prefix)
        has_list_key = self._has_list_key(item_prefix)

        if len([x for x in (has_terminal_key, has_dict_key, has_list_key) if x]) > 1:
            key_types = (
                (['terminal'] if has_terminal_key else []) +
                (['dict'] if has_dict_key else []) +
                (['list'] if has_list_key else []))
            raise Exception("{!r} has duplicate key types {!r}".format(item_prefix, key_types))

        if has_terminal_key:
            return self._underlying[item_path.value().key()]
        elif has_dict_key:
            return JsonFlatteningDict(self._underlying, prefix=item_path.key())
        elif has_list_key:
            return JsonFlatteningList(self._underlying, prefix=item_path.key())
        else:
            item_type = item_path.prefix().path_type()
            if isinstance(item_type, flatpath.DictPrefixPath):
                raise KeyError(item_path.prefix().key_string())
            elif isinstance(item_type, flatpath.ListPrefixPath):
                raise IndexError(item_path.prefix().index_number())
            else:
                raise ValueError(item_type)

    def _has_dict_key(self, item_prefix):
        return item_prefix + "." in self._underlying

    def _has_list_key(self, item_prefix):
        return item_prefix + "[" in self._underlying

    def _has_terminal_key(self, item_prefix):
        return item_prefix + "=" in self._underlying

    def purge_prefix(self, prefix):
        "Remove everythign in the store that starts with this prefix"
        try:
            key_after = key_after_func(self._underlying)
        except KeyError:
            return

        if key_after:
            self._key_after_purge_prefix(key_after, prefix)
        else:
            self._inefficient_purge_prefix(prefix)

    def _key_after_purge_prefix(self, key_after, prefix):
        if prefix in self._underlying:
            del self._underlying[prefix]

        while True:
            try:
                key = key_after(self._underlying, prefix)
            except KeyError:
                break
            if not key.startswith(prefix):
                break
            else:
                del self._underlying[key]

    def _inefficient_purge_prefix(self, prefix):
        for key in list(self._underlying):
            if key.startswith(prefix):
                del self._underlying[key]


class FakeOrderedDict(dict):
    "An inefficiently 'ordered' dict for testing (allows us to avoid use bsddb"
    def __init__(self):
        self.key_after_called = False


    def key_after(self, target_key):
        keys = sorted(self)
        self.key_after_called = True
        for k in keys:
            if k  > target_key:
                return k
        else:
            raise KeyError(target_key)

class TestFlatDict(unittest.TestCase):
    def test_setting(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d["hello"] = "world"

        self.assertEquals(d["hello"], "world")

    def test_delete(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d["hello"] = "world"
        d["other"] = "otra"
        del d["hello"]

        self.assertEquals(d["other"], "otra")
        with self.assertRaises(KeyError):
            d["hello"]
        self.assertEquals(len(d), 1)


    def test_denesting(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d["key"] = dict(hello=dict(world=1), child=17)
        self.assertEquals(d["key"]["hello"]["world"], 1)
        self.assertEquals(d["key"]["child"], 17)

    def test_missing(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        try:
            d["key"]
        except KeyError as e:
            self.assertEquals(e.args, ("key",))

    def test_list(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d["key"] = list([8, 2])
        self.assertEquals(len(d["key"]), 2)
        d["key"][0] = 8

    def test_modify(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d["key"] = 1
        d["key"] = 2
        d["keycard"] = "card"
        self.assertEquals(d["key"], 2)
        self.assertEquals(d["keycard"], "card")

    def test_child_dict_modification(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d["a"] = {}
        d["a"]["b"] = 4
        d["a"]["b"] = True
        self.assertEquals(d["a"]["b"], True)

    def test_items(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = {}
        self.assertEquals(d['a'].keys(), [])

        d['a']['b'] = 1
        self.assertEquals(d['a']['b'], 1)
        self.assertEquals(d['a'].keys(), ['b'])

        d['a']['bat'] = 2
        self.assertEquals(set(d['a'].keys()), set(['bat', 'b']))

    def test_items(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['ibbl'] = True
        d['ibbl'] = None
        d['ibbl'] = None
        d['j'] = 'afcjmbejagddjgdlmfelbmkalbhclie'
        d['j'] = {}
        self.assertEquals(python_copy.copy(d), {'ibbl': None, 'j': {}})

    def test_dict_modify(self):
        d = JsonFlatteningDict(dict())
        d['a'] = None
        d['b'] = 1
        d['a'] = 2
        dict_copy = python_copy.copy(d)
        self.assertEquals(dict_copy, {'b': 1, 'a': 2})

    def test_unordered_dict_pop(self):
        d = JsonFlatteningDict(dict())
        d['a'] = None
        d['b'] = 1
        d.pop('a')
        dict_copy = python_copy.copy(d)
        self.assertEquals(dict_copy, {'b': 1})

    def test_insert(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = []

        d['a'].insert(0, [])

        self.assertEquals(len(d['a'][0]), 0)

    def test_child_iter(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = {}
        d['b'] = 1
        self.assertEquals(list(d['a']),  [])

    def test_list_del(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = []
        d['a'].append(0)
        d['a'].append(1)
        d['a'].append(2)

        del d['a'][1]
        self.assertEquals(d['a'][0], 0)
        self.assertEquals(d['a'][1], 2)
        self.assertEquals(len(d['a']), 2)

    def test_negative_indexing(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = []
        d['a'].append(0)
        d['a'].append(1)
        d['a'].append(2)
        self.assertEquals(d['a'][-1], 2)
        self.assertEquals(d['a'][-2], 1)

    def test_pop(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = []
        d['a'].insert(0, 17)
        d['a'].pop()
        self.assertEquals(len(d['a']), 0)

    def test_copy(self):
        # We unpack and copy list and dictionary
        #   structures (breaks mutability) but
        #   there isn't really a better option
        d = JsonFlatteningDict(FakeOrderedDict())
        lst = []
        dct = dict()
        d['list'] = lst
        d['dict'] = dct
        lst.append(1)
        dct['random'] = 10
        self.assertEquals(len(d['list']), 0)
        self.assertEquals(len(d['dict']), 0)

    def test_nested_copy(self):
        # Make sure that copy works for
        #   nested structures
        d = JsonFlatteningDict(FakeOrderedDict())
        contained_dict = {'value': 17}
        nested = dict(list=[contained_dict])
        d['nested'] = nested
        contained_dict['value'] = 19
        self.assertEquals(d['nested']['list'][0]['value'], 17)

    def test_list_length(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['nested'] = []
        self.assertEquals(len(d), 1)
        d['nested'].append([])
        self.assertEquals(len(d['nested']), 1)

    def test_moving_nested(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = []
        d['a'].insert(0, [])
        d['a'].insert(0, [])

    def test_list_pop(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = []
        d['a'].insert(0, [])
        d['a'].pop()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
