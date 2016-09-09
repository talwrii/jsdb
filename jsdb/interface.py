import collections
import abc

# This is mostly just for documentation
class JsdbStorageInterface(collections.MutableMapping):
    "Interface to store string key value pairs to disk"
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def __init__(self, filename):
        pass

    @abc.abstractmethod
    def close(self):
        pass

    @abc.abstractmethod
    def key_after(self, target_key):
        "Return the key strictly after `target_key`"

