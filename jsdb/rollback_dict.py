import collections
import copy
import unittest
import types

from . import python_copy

class _Deleted(object):
    def __repr__(self):
        return '<DELETED>'

DELETED = _Deleted()

class RollbackableMixin(object):
    def __getitem__(self, key):
        stored = self._get_item(key)

        if stored == DELETED:
            raise KeyError(key)

        if not isinstance(stored, (dict, types.NoneType, list, float, int, str, unicode, RollbackDict, RollbackList)):
            print repr(stored)
            raise ValueError(stored)
        if isinstance(stored, dict):
            result = RollbackDict(stored)
            self[key] = result
            return result
        elif isinstance(stored, list):
            result = RollbackList(stored)
            self[key] = result
            return result
        else:
            return stored


class RollbackDict(RollbackableMixin, collections.MutableMapping):
    "A proxy for changing an underlying data structure that commit and rollback"
    def __init__(self, prototype):
        self._prototype = prototype
        self._updates = {}

    def _items(self):
        return self.items()

    def _get_item(self, key):
        if key in self._updates:
            return self._updates[key]
        else:
            return self._prototype[key]

    def __setitem__(self, key, value):
        self._updates[key] = value

    def __iter__(self):
        for key, value in self._updates.items():
            if value != DELETED:
                yield key

        for key in self._prototype:
            if key not in self._updates:
                yield key

    def __delitem__(self, key):
        self._updates[key] = DELETED

    def __len__(self):
        additions = len([x for x in self._updates.values() if x not in self._prototype])
        deletions = len([x for x in self._updates.values() if x == DELETED])
        return len(self._prototype) + additions - deletions

    def commit(self):
        for k, v in self._updates.items():
            self._prototype[k] = v
        self._updates.clear()

    def python_copy(self):
        return python_copy.dict_copy(self)


class RollbackList(RollbackableMixin, collections.MutableSequence):
    """A proxy for changing an underlying data structure that supports commit and rollback

    This works by creating a complete clone of the underlying list. Simplifying slicing etc
    """

    def __init__(self, underlying):
        self._underlying = underlying
        self._new = None

    def insert(self, index, obj):
        self._ensure_copied()
        self._new.insert(index, obj)

    def _new_items(self):
        return list(enumerate(self._new))

    def _empty_store(self):
        del self._underlying[:]

    def __setitem__(self, key, value):
        self._ensure_copied()
        self._new[key] = value

    def _get_item(self, key):
        self._ensure_copied()
        return self._new[key]

    def _ensure_copied(self):
        if self._new is None:
            self._new = copy.copy(self._underlying)

    def __delitem__(self, key):
        self._ensure_copied()
        del self._new[key]

    def __iter__(self):
        if self._new is not None:
            return iter(self._new)
        else:
            return iter(self._underlying)

    def __len__(self):
        if self._new is not None:
            return len(self._new)
        else:
            return len(self._underlying)

    def commit(self):
        self._underlying[:] = self._new
        self._new = None

class TestRollback(unittest.TestCase):
    def test_rollback_dict(self):
        under = dict(a=1)
        roll = RollbackDict(under)
        self.assertEquals(roll['a'], 1)
        roll['b'] = 2
        roll['a'] = 4
        self.assertEquals(roll['a'], 4)
        self.assertEquals(under['a'], 1)
        self.assertEquals(roll['b'], 2)
        self.assertTrue('b' not in under)
        roll.commit()
        self.assertEquals(under, dict(a=4, b=2))

    def test_rollback_list(self):
        under = []
        lst = RollbackList(under)
        lst.append(1)
        self.assertEquals(under, [])
        self.assertEquals(list(lst), [1])
        self.assertEquals(len(lst), 1)
        self.assertEquals(lst[0], 1)
        lst.commit()
        self.assertEquals(under, [1])
        self.assertEquals(list(lst), [1])

    def test_rollback_dict_indirect(self):
        under = dict(a=dict(b=1))
        roll = RollbackDict(under)

        roll['a']['b'] = 2
        self.assertEquals(under['a']['b'], 1)
        self.assertEquals(roll['a']['b'], 2)
        proxy = roll['a']

        roll.commit()

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
        roll.commit()
        self.assertTrue(list(under) == [1])


if __name__ == '__main__':
    unittest.main()
