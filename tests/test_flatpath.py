import unittest

from jsdb.flatpath import FlatPath, IncorrectType, RootNode

class FlatPathTest(unittest.TestCase):
    def test_parent(self):
        self.assertEquals(FlatPath('."hello"[0]').parent(), FlatPath('."hello"'))

    def test_basic(self):
        self.assertEquals(FlatPath('."hello"').parent(), FlatPath(''))
        self.assertEquals(FlatPath('."hello"').value(), FlatPath('."hello"='))

        with self.assertRaises(IncorrectType):
            FlatPath('."hello"=').value()

        with self.assertRaises(RootNode):
            FlatPath('').parent()

        with self.assertRaises(RootNode):
            FlatPath('#').prefix().parent()

        self.assertEquals(FlatPath('."hello"').value(), FlatPath('."hello"='))
        self.assertEquals(FlatPath('."hello"').dict(), FlatPath('."hello".'))
        self.assertEquals(FlatPath('."hello"').prefix(), FlatPath('."hello"'))
        self.assertEquals(FlatPath('."hello"#').prefix(), FlatPath('."hello"'))
        self.assertEquals(FlatPath('."hello"=').prefix(), FlatPath('."hello"'))
        self.assertEquals(FlatPath('."hello".').prefix(), FlatPath('."hello"'))

    def test_depth(self):
        self.assertEquals(FlatPath('."hello"').depth(), 1)
        self.assertEquals(FlatPath('."hello"."two"').depth(), 2)
        self.assertEquals(FlatPath('."hello"."two"[0]').depth(), 3)

if __name__ == '__main__':
	unittest.main()
