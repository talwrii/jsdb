
import shutil
import tempfile
import unittest

from jsdb.leveldict import LevelDict


class LevelDictTest(unittest.TestCase):
    def test_basic(self):
        name = tempfile.mkdtemp()
        try:
            db = LevelDict(name)

            db['hello'] = 'world'
            self.assertEquals(db['hello'], 'world')

            db.close()
            db = LevelDict(name)

            self.assertEquals(db['hello'], 'world')

            del db['hello']

            try:
                print db['hello']
            except KeyError as e:
                self.assertEquals(e.args, ('hello',))

            db.close()
            db = LevelDict(name)
            with self.assertRaises(KeyError):
                print db['hello']

            db['hello'] = 'world'
            db['hello'] = 'moon'
            self.assertEquals(db['hello'], 'moon')
            db.close()
            db = LevelDict(name)
            self.assertEquals(db['hello'], 'moon')

            self.assertEquals(list(db), ['hello'])
        finally:
            shutil.rmtree(name)


if __name__ == "__main__":
    unittest.main()
