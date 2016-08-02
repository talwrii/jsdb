"""A way to store large json-like object graphs"""

import bsddb
import collections
import json
import logging
import os
import pprint
import random
import shutil
import tempfile
import unittest

from . import python_copy
from .flatpath import FlatPath
from .rollback_dict import RollbackDict

LOGGER = logging.getLogger('jsdb')

ASCII_TOP = '\xff'

class Jsdb(collections.MutableMapping):
    """A file-backed, persisted-object graph supporting json types"""
    def __init__(self, filename):
        self._filename = filename
        self._db = None
        self._data_file = None
        self._closed = False

    def _open(self):
        if self._closed:
            raise DbClosedError()

        if self._db is None:
            self._data_file = bsddb.btopen(self._filename, 'w')
            self._db = RollbackDict(JsonEncodeDict(self._data_file))

    def __getitem__(self, key):
        self._open()
        return self._db[key]

    def __setitem__(self, key, value):
        self._open()
        self._db[key] = value

    def __len__(self):
        return len(self._db)

    def __iter__(self):
        return iter(self._db)

    def __delitem__(self, key):
        del self._db[key]

    def commit(self):
        self._db.commit()

    def close(self):
        if self._data_file:
            self._data_file.close()
        self._data_file = None
        self._db = None
        self._closed = True

    def python_copy(self):
        """Return a copy of the entire structure without backed proxies"""
        return self._db.python_copy()

class DbClosedError(Exception):
    """Database is closed"""

class JsonEncodeDict(collections.MutableMapping):
    "Convert basic json data types to and from strings. To deal with a dictioanry that only accepts string values"
    def __init__(self, underlying):
        self._underlying = underlying

    def __getitem__(self, key):
        return self._decode(self._underlying[key])

    def __setitem__(self, key, value):
        self._underlying[key] = self._encode(value)

    def _decode(self, string):
        return json.loads(string)

    def _encode(self, value):
        if not isinstance(value, (int, float, str, bool)):
            raise ValueError(value)
        return json.dumps(value)

    def __len__(self):
        return len(self._underlying)

    def __delitem__(self, key):
        del self._underlying[key]

    def __iter__(self):
        return iter(self._underlying)

class TestJsdb(unittest.TestCase):
    def setUp(self):
        self.direc = tempfile.mkdtemp()
        self._filename = os.path.join(self.direc, 'file.jsdb')

    def tearDown(self):
        shutil.rmtree(self.direc)

    def test_close(self):
        db = Jsdb(self._filename)
        db.close()
        self.assertRaises(DbClosedError, lambda: db['key'])

    def test_basic(self):
        db = Jsdb(self._filename)
        db['key'] = 'value'
        db.commit()
        db.close()

        db = Jsdb(self._filename)
        self.assertEquals(db['key'], 'value')

    def test_float(self):
        db = Jsdb(self._filename)
        db['key'] = 1.0
        db.commit()
        db.close()

        db = Jsdb(self._filename)
        self.assertEquals(db['key'], 1.0)

    def test_flattening_mapping_basic(self):
        store = dict()
        d = flatdict.JsonFlatteningDict(store)

        self.assertFalse("test" in d)
        d["test"] = 1
        self.assertEquals(d["test"], 1)

    def test_flattening_mapping_iter(self):
        store = dict()
        d = flatdict.JsonFlatteningDict(store)
        d["one"] = 1
        d["nested"] = dict(depth=2)
        d["two"] = 2
        self.assertEquals(set(iter(d)), set(["one", "nested", "two"]))

    def test_flattening_mapping_with_sorting(self):
        store = flatdict.FakeOrderedDict()
        d = flatdict.JsonFlatteningDict(store)

        d["one"] = 1
        d["nested"] = dict(depth=2)
        d["two"] = 2

        self.assertEquals(set(iter(d)), set(["one", "nested", "two"]))
        self.assertTrue(store.key_after_called)


class JsdbFuzzTest(unittest.TestCase):
    def setUp(self):
        self.direc = tempfile.mkdtemp()
        self._filename = os.path.join(self.direc, 'file.jsdb')
        self.maxDiff = 1300

    def test_fuzz(self):
        # to have confidence that this actually works
        #   we will perform random insertions and deletions
        #   and check that the structure matches a normal json options

        json_dict = dict()
        db = Jsdb(self._filename)

        while True:
            paths = list(self.dict_insertion_path(json_dict))
            path = random.choice(paths)
            action = self.random_path_action(path)

            LOGGER.debug('Fuzz action %s %r', action, path)

            if action == 'dict-insert':
                key = self.random_key()
                value = self.random_value()
                LOGGER.debug('Inserting %r -> %r', key, value)
                self.lookup_path(db, path)[key] = value
                self.lookup_path(json_dict, path)[key] = value
            elif action == 'list-insert':
                value = self.random_value()
                LOGGER.debug('Inserting %r', value)
                json_lst = self.lookup_path(json_dict, path)
                db_list = self.lookup_path(db, path)
                point = random.randint(0, len(json_lst))
                json_lst.insert(point, value)
                db_list.insert(point, value)
            elif action == 'list-pop':
                value = self.random_value()
                lst = self.lookup_path(json_dict, path)
                db_list = self.lookup_path(db, path)
                if lst:
                    lst.pop()
                    db_list.pop()
            elif action == 'dict-modify':
                value = self.random_value()
                self.set_path(db, path, value)
                self.set_path(json_dict, path, value)
            elif action == 'dict-delete':
                self.set_path(db, path, None, delete=True)
                self.set_path(json_dict, path, None, delete=True)
            else:
                raise ValueError(action)

            # LOGGER.debug('%s', pprint.pformat(json_dict))
            self.assertEquals(python_copy.copy(db), json_dict)

    def random_key(self):
        length = random.randint(0, 40)
        return ''.join([random.choice('abcdefghijklm') for _ in range(length)])

    def random_value(self):
        value_type = weighted_random_choice(dict(str=1, int=1, float=1, bool=1, dict=1, list=1, none=1))
        if value_type == 'str':
            return self.random_key()
        elif value_type == 'int':
            return random.randint(-1000, 1000)
        elif value_type == 'float':
            return (random.random() - 0.5) * 1000
        elif value_type == 'none':
            return None
        elif value_type == 'dict':
            return dict()
        elif value_type == 'list':
            return list()
        elif value_type == 'bool':
            return random.choice([True, False])
        else:
            raise ValueError(value_type)

    def random_path_action(self, (type, raw_path)):
        if type == 'dict':
            return 'dict-insert'
        elif type == 'dict-key':
            return weighted_random_choice({
                'dict-modify': self.DICT_MODIFY_WEIGHT,
                'dict-delete': self.DICT_DEL_WEIGHT})
        elif type == 'list':
            return weighted_random_choice({
                'list-insert': self.DICT_MODIFY_WEIGHT,
                'list-pop': self.DICT_DEL_WEIGHT})
        else:
            raise ValueError(type)

    DICT_MODIFY_WEIGHT = 5
    DICT_DEL_WEIGHT = 1

    def lookup_path(self, data, (type, raw_path)):
        d = data
        for k in raw_path:
            d = d[k]
        return d

    def set_path(self, data, (type, raw_path), value, delete=False):
        d = data
        for k in raw_path[:-1]:
            d = d[k]

        if delete:
            del d[raw_path[-1]]
        else:
            d[raw_path[-1]] = value

    @classmethod
    def dict_insertion_path(cls, d):
        yield ('dict', ())
        for k in d:
            if not isinstance(k, str):
                raise ValueError(k)
            if isinstance(d[k], dict):
                for descendant_path in cls.dict_insertion_path(d[k]):
                    action, path = descendant_path
                    yield action, (k,) + path
            elif isinstance(d[k], list):
                for descendant_path in cls.list_insertion_path(d[k]):
                    action, path = descendant_path
                    yield action, (k,) + path
            else:
                yield 'dict-key', (k,)

    @classmethod
    def list_insertion_path(cls, d):
        yield ('list', ())
        for i, v in enumerate(d):
            if isinstance(v, dict):
                for descendant_path in cls.dict_insertion_path(v):
                    action, path = descendant_path
                    yield action, (i,) + path
            elif isinstance(v, list):
                for path in cls.list_insertion_path(v):
                    action, path = descendant_path
                    yield action, (i,) + path
            else:
                yield 'list-item', (i,)


def weighted_random_choice(weights):
    rand = random.random() * sum(weights.values())
    total = 0
    for key in sorted(weights):
        total += weights[key]
        if rand <= total:
            return key
    else:
        raise Exception('Should never be reached')

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
