"""A dictionary that flattens a nested key-value mappings and lists into a store that does not support nesting.
"""

import collections
import logging
import unittest

from . import python_copy
from .flatpath import FlatPath
from . import flatpath
from .data import JSON_VALUE_TYPES
from . import treeutils

LOGGER = logging.getLogger('jsdb.flatdict')

ASCII_TOP = '\xff'

class JsonFlatteningDict(collections.MutableMapping):
    "Flatten nested list and dictionaries down to a string to value mapping"

    # The format of the keys is
    #   path := dot (dict_key (path | equals | pound))? | bracket (list_index (path | equals | pound)) |
    #   list_index := integer right_bracket
    #   dict_key := " dict_key_string "
    #   `equals` is the string "="
    #   `bracket` is the string "["
    #   `dict_key_string` python escape string

    # Example

    # ."hello"[0]."world"=
    #     stores the value of d["hello"][0]["world"]

    # ."hello"#
    #     stores the the length of the dictionary or list d["hello"]

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
        return self._underlying.get(self._path.length().key(), 0)

    def _set_length(self, value):
        self._underlying[self._path.length().key()] = value

    def __iter__(self):
        key_after = treeutils.key_after_func(self._underlying)
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
        try:
            return child_path.prefix().parent().key() == self._prefix
        except flatpath.RootNode:
            return False

    def _key_after_iter(self, key_after):
        # If we can do ordering-based lookups (and hence
        #   prefix-based) queries efficiently then
        #   iter becomes a lot more efficient

        # Commence literate programming! (Too complicated to
        #   be understood with code alone)

        # We start with something like "a"
        #     We want to find something like "a"."b"
        #     but not "a". or "a"#

        # So we search for things after "a".
        #   the result found is guaranteed to be a child
        #   because "a"."b". and "a"."b"[ precede
        #   their descendants
        try:
            found_key = key_after(self._path.dict().key())
            child_path = FlatPath(found_key)
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
                child_key = key_after(child_path.key() + ASCII_TOP)
                child_path = FlatPath(child_key)
            except KeyError:
                break

    def __delitem__(self, key):
        if key not in self:
            raise KeyError(key)
        else:
            self._flat_store.purge_prefix(self._path.dict().lookup(key).key())
            self._set_length(len(self) - 1)

    def __setitem__(self, key, value):
        #LOGGER.debug('%r: Setting %r -> %r', self, key, value)
        if isinstance(key, unicode):
            key = key.encode('ascii')

        if not isinstance(key, str):
            raise ValueError(key)

        # Special case: no-op self assignment. e.g. d["a"] = d["a"]
        if isinstance(value, (JsonFlatteningDict, JsonFlatteningList)):
            if self._path.dict().lookup(key).key() == value._path.key():
                return

        # Deepcopy first to allow assignment from within
        #    ourselves. e.g. d["a"] = d["a"]["child"]
        if isinstance(value, (collections.Sequence, collections.Mapping)):
            value = python_copy.copy(value)

        if isinstance(value, JSON_VALUE_TYPES):
            self.pop(key, None)
            flat_key = self._path.dict().lookup(key).value().key()
            self._underlying[flat_key] = value
            self._set_length(len(self) + 1)
        elif isinstance(value, (dict, collections.MutableMapping)):
            self.pop(key, None)
            base_path = self._path.dict().lookup(key)
            self._underlying[base_path.dict().key()] = True
            self._set_length(len(self) + 1)
            dict_store = self[key]
            for dict_key in list(value):
                dict_store[dict_key] = value[dict_key]
        elif isinstance(value, (list, collections.MutableSequence)):
            self.pop(key, None)
            base_path = self._path.dict().lookup(key)
            self._underlying[base_path.list().key()] = True
            self._set_length(len(self) + 1)

            list_store = self[key]
            for item in list(value):
                list_store.append(item)
        else:
            raise ValueError(value)

    def copy(self):
        return {k: self[k] for k in self.keys()}


class JsonFlatteningList(collections.MutableSequence):
    def __init__(self, underlying, prefix):
        self._prefix = prefix
        self._underlying = underlying
        self._flat_store = FlatteningStore(self._underlying)
        self._path = FlatPath(prefix)

    def __repr__(self):
        return '<JsonFlatteningList path={!r}>'.format(self._prefix)

    def __getitem__(self, index):
        index = self._simplify_index(index)
        return self._getitem(index)

    def __len__(self):
        return self._underlying.get(self._path.length().key(), 0)

    def _set_length(self, value):
        self._underlying[self._path.length().key()] = value

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
        # special case no-op self: assignment
        #   a[1] = a[1]
        if isinstance(value, (JsonFlatteningDict, JsonFlatteningList)):
            if self._path.list().index(index).key() == value._path.key():
                return

        if isinstance(value, (collections.Sequence, collections.Mapping)):
            value = python_copy.copy(value)

        if isinstance(index, slice):
            if index.start == index.stop == index.step == None:
                # Support complete reassignment because

                self._flat_store.purge_prefix(self._path.list().key())
                self._underlying[self._path.list().key()] = True

                self._set_length(0)

                for item in value:
                    self.append(item)
            else:
                raise NotImplementedError()
        else:
            self._set_item(index, value)

    def _set_item(self, index, value, check_index=True):
        if check_index:
            if not 0 <= index < len(self):
                raise IndexError('assignment out of range')

        # Deepcopy first to allow assignment from within
        #    ourselves. e.g. d["a"] = d["a"]["child"]
        if isinstance(value, (collections.Sequence, collections.Mapping)):
            value = python_copy.copy(value)

        self._flat_store.purge_prefix(self._path.list().index(index).key())

        if isinstance(value, JSON_VALUE_TYPES):
            self._underlying[self._path.list().index(index).value().key()] = value
        elif isinstance(value, dict):
            dict_key = self._path.list().index(index)
            self._underlying[dict_key.dict().key()] = True
            nested_dict = self[index]
            for key, nested_value in list(value.items()):
                nested_dict[key] = nested_value
        elif isinstance(value, list):
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

        self._set_length(length - 1)

    def insert(self, pos, value):
        # We need to do our own value shifting
        inserted_value = value
        length = len(self)
        # Copy upwards to avoid temporary values

        self._set_length(length + 1)

        for i in range(length, pos, -1):
            self._set_item(i, self[i - 1], check_index=False)

        self._set_item(pos, inserted_value, check_index=False)



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
            key_after = treeutils.key_after_func(self._underlying)
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
                key = key_after(prefix)
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
