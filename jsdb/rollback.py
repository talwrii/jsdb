import collections

from .data import JSON_TYPES

class _Deleted(object):
    def __repr__(self):
        return '<DELETED>'

DELETED = _Deleted()

class _RollbackMixin(object):
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

class RollbackDict(_RollbackMixin, collections.MutableMapping):
    "A proxy for changing an underlying data structure that commit and rollback"
    def __init__(self, underlying, parent=None):
        self._underlying = underlying
        self._updates = {}
        self._parent = parent
        self._changed_descendents = []

    def _items(self):
        return self.items()

    def __getitem__(self, key):
        if key in self._updates:
            updated =  self._updates[key]
            if updated == DELETED:
                raise KeyError(key)
            else:
                return updated
        else:
            stored = self._underlying[key]
            wrapped = self._rollback_wrap(stored)
            if isinstance(wrapped, _RollbackMixin):
                self._updates[key] = wrapped

            return wrapped

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
        for key, value in self._updates.iteritems():
            if value != DELETED:
                yield key

        for key in self._underlying:
            if key not in self._updates:
                yield key

    def __delitem__(self, key):
        if key in self and self._updates.get(key, None) != DELETED:
            self._updates[key] = DELETED
        else:
            raise KeyError(key)

    def __len__(self):
        additions = len([x for x in self._updates.keys() if x not in self._underlying])
        deletions = len([x for x in self._updates.values() if x == DELETED])
        return len(self._underlying) + additions - deletions

    def commit(self):
        if self._parent is not None:
            raise Exception('Can only commit at top level')
        self._commit()

    def rollback(self):
        if self._parent is not None:
            raise Exception('Can only commit at top level')
        self._rollback()

    def _rollback(self):
        for desc in self._changed_descendents:
            desc._rollback()
        self._updates.clear()

    def _commit(self):
        for desc in self._changed_descendents:
            desc._commit() # pylint: disable=protected-access
        del self._changed_descendents[:]

        # There was a logic bug here related to
        #    update / delete order. This might
        #    deserve some proof.
        for k, v in list(self._updates.items()): # python3
            if v == DELETED:
                pass
            else:
                if isinstance(v, _RollbackMixin):
                    v._commit() # pylint: disable=protected-access
                    self._underlying[k] = v._underlying # pylint: disable=protected-access
                else:
                    self._underlying[k] = v
                self._updates.pop(k)

        for k, v in list(self._updates.items()): # python3
            if v != DELETED:
                raise ValueError(k)
            del self._underlying[k]
        self._updates.clear()

class RollbackList(_RollbackMixin, collections.MutableSequence):
    """A proxy for changing an underlying data structure that supports commit and rollback

    This works by creating a complete clone of the underlying list. Simplifying slicing etc
    """

    def __init__(self, underlying, parent=None):
        self._underlying = underlying
        self._new = None
        self._parent = parent

    def insert(self, index, obj):
        self._ensure_copied()
        self._record_changed(self)
        self._new.insert(index, obj)

    def _new_items(self):
        return list(enumerate(self._new))

    def _empty_store(self):
        del self._underlying[:]

    def __setitem__(self, key, value):
        self._ensure_copied()
        self._record_changed(self)
        self._new[key] = value

    def __getitem__(self, key):
        self._ensure_copied()
        value = self._new[key]
        wrapped = self._rollback_wrap(value)
        if value == wrapped:
            return value
        else:
            self._new[key] = wrapped
            return wrapped

    def _ensure_copied(self):
        if not self._is_updated():
            self._new = list(self._underlying)

    def __delitem__(self, key):
        self._ensure_copied()
        self._record_changed(self)
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
            self._parent._record_changed(item) # pylint: disable=protected-access

    def _commit(self):
        if self._is_updated():
            new_values = []
            for x in self._new:
                if isinstance(x, _RollbackMixin):
                    # Ensure that children are commit before us
                    x._commit() # pylint: disable=protected-access
                    new_values.append(x._underlying)  # pylint: disable=protected-access
                else:
                    new_values.append(x)

            self._underlying[:] = new_values
        self._new = None

    def _rollback(self):
        self._new = None
