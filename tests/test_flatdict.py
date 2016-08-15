import unittest

from jsdb.flatdict import JsonFlatteningDict
from jsdb import python_copy

from testutils import FakeOrderedDict

class TestFlatDict(unittest.TestCase):
    def test_setting(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d["hello"] = "world"

        self.assertEquals(d["hello"], "world")

    def test_delete(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d["hello"] = "world"
        d["other"] = "otra"
        del d["hello"]

        self.assertEquals(d["other"], "otra")
        with self.assertRaises(KeyError):
            d["hello"]
        self.assertEquals(len(d), 1)


    def test_denesting(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d["key"] = dict(hello=dict(world=1), child=17)
        self.assertEquals(d["key"]["hello"]["world"], 1)
        self.assertEquals(d["key"]["child"], 17)

    def test_missing(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        try:
            d["key"]
        except KeyError as e:
            self.assertEquals(e.args, ("key",))

    def test_list(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d["key"] = list([8, 2])
        self.assertEquals(len(d["key"]), 2)
        d["key"][0] = 8

    def test_modify(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d["key"] = 1
        d["key"] = 2
        d["keycard"] = "card"
        self.assertEquals(d["key"], 2)
        self.assertEquals(d["keycard"], "card")

    def test_child_dict_modification(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d["a"] = {}
        d["a"]["b"] = 4
        d["a"]["b"] = True
        self.assertEquals(d["a"]["b"], True)

    def test_items(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = {}
        self.assertEquals(d['a'].keys(), [])

        d['a']['b'] = 1
        self.assertEquals(d['a']['b'], 1)
        self.assertEquals(d['a'].keys(), ['b'])

        d['a']['bat'] = 2
        self.assertEquals(set(d['a'].keys()), set(['bat', 'b']))

    def test_items2(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['ibbl'] = True
        d['ibbl'] = None
        d['ibbl'] = None
        d['j'] = 'afcjmbejagddjgdlmfelbmkalbhclie'
        d['j'] = {}
        self.assertEquals(python_copy.copy(d), {'ibbl': None, 'j': {}})

    def test_dict_modify(self):
        d = JsonFlatteningDict(dict())
        d['a'] = None
        d['b'] = 1
        d['a'] = 2
        dict_copy = python_copy.copy(d)
        self.assertEquals(dict_copy, {'b': 1, 'a': 2})

    def test_unordered_dict_pop(self):
        d = JsonFlatteningDict(dict())
        d['a'] = None
        d['b'] = 1
        d.pop('a')
        dict_copy = python_copy.copy(d)
        self.assertEquals(dict_copy, {'b': 1})

    def test_insert(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = []

        d['a'].insert(0, [])

        self.assertEquals(len(d['a'][0]), 0)

    def test_child_iter(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = {}
        d['b'] = 1
        self.assertEquals(list(d['a']),  [])

    def test_list_del(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = []
        d['a'].append(0)
        d['a'].append(1)
        d['a'].append(2)

        del d['a'][1]
        self.assertEquals(d['a'][0], 0)
        self.assertEquals(d['a'][1], 2)
        self.assertEquals(len(d['a']), 2)

    def test_negative_indexing(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = []
        d['a'].append(0)
        d['a'].append(1)
        d['a'].append(2)
        self.assertEquals(d['a'][-1], 2)
        self.assertEquals(d['a'][-2], 1)

    def test_pop(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = []
        d['a'].insert(0, 17)
        d['a'].pop()
        self.assertEquals(len(d['a']), 0)

    def test_copy(self):
        # We unpack and copy list and dictionary
        #   structures (breaks mutability) but
        #   there isn't really a better option
        d = JsonFlatteningDict(FakeOrderedDict())
        lst = []
        dct = dict()
        d['list'] = lst
        d['dict'] = dct
        lst.append(1)
        dct['random'] = 10
        self.assertEquals(len(d['list']), 0)
        self.assertEquals(len(d['dict']), 0)

    def test_nested_copy(self):
        # Make sure that copy works for
        #   nested structures
        d = JsonFlatteningDict(FakeOrderedDict())
        contained_dict = {'value': 17}
        nested = dict(list=[contained_dict])
        d['nested'] = nested
        contained_dict['value'] = 19
        self.assertEquals(d['nested']['list'][0]['value'], 17)

    def test_list_length(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['nested'] = []
        self.assertEquals(len(d), 1)
        d['nested'].append([])
        self.assertEquals(len(d['nested']), 1)

    def test_moving_nested(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = []
        d['a'].insert(0, [])
        d['a'].insert(0, [])

    def test_list_pop(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = []
        d['a'].insert(0, [])
        d['a'].pop()

    def test_nested_list_insert(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['a'] = []
        d['a'].insert(0, [])
        d['a'][0].insert(0, None)
        d['a'].insert(0, 'f')
        self.assertEquals(python_copy.copy(d['a']), ['f', [None]])

    def test_dict_moving(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d['b'] = []
        d['b'].insert(0, {})
        d['b'][0]['c'] = {}
        d['b'].insert(0, 'test')

    def test_flattening_mapping_basic(self):
        store = dict()
        d = JsonFlatteningDict(store)

        self.assertFalse("test" in d)
        d["test"] = 1
        self.assertEquals(d["test"], 1)

    def test_flattening_mapping_with_sorting(self):
        store = FakeOrderedDict()
        d = JsonFlatteningDict(store)

        d["one"] = 1
        d["nested"] = dict(depth=2)
        d["two"] = 2

        self.assertEquals(set(iter(d)), set(["one", "nested", "two"]))
        self.assertTrue(store.key_after_called)

    def test_flattening_mapping_iter(self):
        store = dict()
        d = JsonFlatteningDict(store)
        d["one"] = 1
        d["nested"] = dict(depth=2)
        d["two"] = 2
        self.assertEquals(set(iter(d)), set(["one", "nested", "two"]))

    def test_slice_assign(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d["a"] = ["one", "two"]
        reference = d["a"]
        d["a"][:] = [1, 2, 3]
        self.assertEquals(reference[1], 2)

    def test_iter(self):
        d = JsonFlatteningDict(FakeOrderedDict())
        d["a"] = 1
        d["b"] = {'blah': 1}
        d["c"] = ["list", "item"]
        self.assertEquals(sorted(d.keys()), ["a", "b", "c"])


if __name__ == '__main__':
    unittest.main()
