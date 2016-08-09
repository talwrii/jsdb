import collections
import unittest

from . import python_copy
from .data import JSON_TYPES

class _Deleted(object):
    def __repr__(self):
        return '<DELETED>'

DELETED = _Deleted()

class RollbackableMixin(object):
    def __getitem__(self, key):
        stored = self._get_item(key)

        if stored == DELETED:
            raise KeyError(key)

        return self._rollback_wrap(stored)

    def _rollback_wrap(self, value):
        "Make the value rollbackable"

        if not isinstance(value, JSON_TYPES):
            raise ValueError(value)
        elif isinstance(value, collections.MutableMapping):
            if isinstance(value, RollbackDict):
                return value
            else:
                return RollbackDict(value, parent=self)
        elif isinstance(value, collections.MutableSequence):
            if isinstance(value, RollbackList):
                return value
            else:
                return RollbackList(value, parent=self)
        else:
            return value

class RollbackDict(RollbackableMixin, collections.MutableMapping):
    "A proxy for changing an underlying data structure that commit and rollback"
    def __init__(self, underlying, parent=None):
        self._underlying = underlying
        self._updates = {}
        self._parent = parent
        self._changed_descendents = []

    def _items(self):
        return self.items()

    def _get_item(self, key):
        if key in self._updates:
            return self._updates[key]
        else:
            return self._underlying[key]

    def __setitem__(self, key, value):
        if self._parent:
            self._parent._record_changed(self) # pylint: disable=protected-access
        self._updates[key] = self._rollback_wrap(value)

    def _record_changed(self, item):
        if self._parent:
            self._parent._record_changed(item) # pylint: disable=protected-access
        else:
            self._changed_descendents.append(item)

    def __iter__(self):
        for key, value in self._updates.items():
            if value != DELETED:
                yield key

        for key in self._underlying:
            if key not in self._updates:
                yield key

    def __delitem__(self, key):
        self._updates[key] = DELETED

    def __len__(self):
        additions = len([x for x in self._updates.keys() if x not in self._underlying])
        deletions = len([x for x in self._updates.values() if x == DELETED])
        return len(self._underlying) + additions - deletions

    def commit(self):
        if self._parent is not None:
            raise Exception('Can only commit at top level')
        self._commit()

    def _commit(self):
        for desc in self._changed_descendents:
            desc._commit()

        for k, v in self._updates.items():
            if v == DELETED:
                del self._underlying[k]
            else:
                if isinstance(v, RollbackableMixin):
                    v._commit()
                    self._underlying[k] = v._underlying
                else:
                    self._underlying[k] = v
        self._updates.clear()

    def python_copy(self):
        return python_copy.dict_copy(self)

class RollbackList(RollbackableMixin, collections.MutableSequence):
    """A proxy for changing an underlying data structure that supports commit and rollback

    This works by creating a complete clone of the underlying list. Simplifying slicing etc
    """

    def __init__(self, underlying, parent=None):
        self._underlying = underlying
        self._new = None
        self._parent = parent

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
        if self._parent:
            self._parent._record_changed(self)
        if not self._is_updated():
            self._new = list(self._underlying)

    def __delitem__(self, key):
        self._ensure_copied()
        del self._new[key]

    def __iter__(self):
        if self._is_updated():
            return iter(self._new)
        else:
            return iter(self._underlying)

    def __len__(self):
        if self._is_updated():
            return len(self._new)
        else:
            return len(self._underlying)

    def _is_updated(self):
        return self._new is not None

    def _record_changed(self, item):
        if self._parent:
            self._parent._record_changed(item)

    def _commit(self):
        if self._is_updated():
            self._underlying[:] = self._new
        self._new = None

class TestRollback(unittest.TestCase):

    def _commit(self, item):
        item._commit()  # pylint: disable=protected-access

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

    def test_rollback_dict_indirect(self):
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
