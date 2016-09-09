"Leveldb dictionary interface, like bsddb"

import plyvel

from . import interface

class LevelDict(interface.JsdbStorageInterface):
    def __init__(self, filename):
        interface.JsdbStorageInterface.__init__(self, filename)
        self._db = plyvel.DB(filename, create_if_missing=True)

    def __setitem__(self, key, value):
        self._db.put(key, value)

    def __iter__(self):
        for key, _value in self._db.iterator():
            yield key

    def __len__(self):
        i = 0
        for i, _ in enumerate(self._db.iterator()):
            i += 1
        return i

    def __getitem__(self, key):
        result = self._db.get(key)
        if result is None:
            raise KeyError(key)
        else:
            return result

    def __delitem__(self, key):
        self.__getitem__(key)
        self._db.delete(key) # delete does not raise on error

    def close(self):
        self._db.close()

    def key_after(self, target_key):
        for key, _ in self._db.iterator(start=target_key):
            if key == target_key:
                continue
            else:
                return key
        else:
            raise KeyError(target_key)
