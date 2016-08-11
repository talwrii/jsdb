import os
import shutil
import tempfile

import unittest

import jsdb.python_copy
from jsdb import Jsdb, DbClosedError

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
        jsdb.python_copy.copy(db)

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

if __name__ == '__main__':
    unittest.main()
