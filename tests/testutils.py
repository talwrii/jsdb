class FakeOrderedDict(dict):
    "An inefficiently 'ordered' dict for testing (allows us to avoid use bsddb"
    def __init__(self):
        self.key_after_called = False

    def key_after(self, target_key):
        keys = sorted(self)
        self.key_after_called = True
        for k in keys:
            if k  > target_key:
                return k
        else:
            raise KeyError(target_key)

