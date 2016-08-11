import unittest

from jsdb.rollback import RollbackDict, RollbackList

class TestRollback(unittest.TestCase):
    def _commit(self, item):
        item._commit()  # pylint: disable=protected-access

    def test_rollback(self):
        under = dict(a=1)
        roll = RollbackDict(under)
        self.assertEquals(roll['a'], 1)
        roll['b'] = 2
        roll['a'] = 4
        self.assertEquals(roll['a'], 4)
        self.assertEquals(under['a'], 1)
        self.assertEquals(roll['b'], 2)
        self.assertTrue('b' not in under)
        self._commit(roll)
        self.assertEquals(under, dict(a=4, b=2))

    def test_rollback_list(self):
        under = []
        lst = RollbackList(under)
        lst.append(1)
        self.assertEquals(under, [])
        self.assertEquals(list(lst), [1])
        self.assertEquals(len(lst), 1)
        self.assertEquals(lst[0], 1)
        self._commit(lst)
        self.assertEquals(under, [1])
        self.assertEquals(list(lst), [1])

    def test_rollback_indirect(self):
        under = dict(a=dict(b=1))
        roll = RollbackDict(under)

        roll['a']['b'] = 2
        self.assertEquals(under['a']['b'], 1)
        self.assertEquals(roll['a']['b'], 2)
        proxy = roll['a']

        self._commit(roll)

        self.assertEquals(under['a']['b'], 2)
        self.assertEquals(roll['a']['b'], 2)
        self.assertEquals(proxy['b'], 2)

    def test_iter(self):
        under = dict(a=dict(b=1))
        roll = RollbackDict(under)
        roll['b'] = 17
        self.assertEquals(set(iter(roll)), set(['a', 'b']))

    def test_delete(self):
        under = dict(a=dict(b=1))
        roll = RollbackDict(under)

        roll['b'] = 17
        del roll['b']
        self.assertFalse('b' in roll)

        del roll['a']
        self.assertFalse('a' in roll)

    def test_list_insert(self):
        under = list()
        roll = RollbackList(under)
        roll.insert(1, 1)
        self.assertFalse(under)
        self.assertTrue(list(roll) == [1])
        self._commit(roll)
        self.assertTrue(list(under) == [1])

    def test_subcommit(self):
        under = dict()
        d = RollbackDict(under)

        d['a'] = {}
        self._commit(d)
        d['a']['b'] = 'dirty'
        self._commit(d)
        self.assertEquals(under['a']['b'], 'dirty')

    def test_subcommit_list(self):
        under = dict()
        d = RollbackDict(under)
        d['a'] = []
        self._commit(d)
        d['a'].insert(0, [])
        self._commit(d)
        d['a'][0].insert(0, [])
        self._commit(d)
        d['a'][0][0].insert(0, 17)
        self._commit(d)
        self.assertEquals(under['a'][0][0][0], 17)

if __name__ == '__main__':
    unittest.main()