"""A way to store large json-like object graphs"""

import bsddb
import collections
import json
import logging
import os
import shutil
import tempfile
import unittest
import types

from . import python_copy
from .rollback_dict import RollbackDict
from . import flatdict
from . import treeutils

LOGGER = logging.getLogger('jsdb')

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
            self._db = RollbackDict(flatdict.JsonFlatteningDict(JsonEncodeDict(self._data_file)))

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
        encoded_value = self._encode(value)
        self._underlying[key] = encoded_value

    def _decode(self, string):
        return json.loads(string)

    def _encode(self, value):
        if not isinstance(value, (int, float, str, bool, types.NoneType, unicode)):
            raise ValueError(value)
        return json.dumps(value)

    def __len__(self):
        return len(self._underlying)

    def __delitem__(self, key):
        del self._underlying[key]

    def __iter__(self):
        return iter(self._underlying)

    def key_after_func(self):
        func = treeutils.key_after_func(self._underlying)
        return func


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

    def test_dict(self):
        db = Jsdb(self._filename)
        db['a'] = {}
        db.commit()
        python_copy.copy(db)

    def test_insert(self):
        d = Jsdb(self._filename)
        d['a'] = []
        d.commit()
        d['a'].insert(0, 17)
        d.commit()
        self.assertEquals(d['a'][0], 17)

    def test_strings(self):
        d = Jsdb(self._filename)
        d[''] = []
        d.commit()
        d[''].insert(0, False)
        d.commit()
        d[''][0] = 'cic'
        d.commit()
        d[''].insert(0, [])
        d.commit()

    def test_fuzz1(self):
        d = Jsdb(self._filename)
        d['a'] = []
        d.commit()
        d['a'].insert(0, [])
        d.commit()
        d['a'][0].insert(0, 17)
        d.commit()
        self.assertEquals(d['a'][0][0], 17)
5

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()
