# We might like to do this with some sort of parser

def escape_double_quote(string):
    return string.replace('\\', '\\\\').replace('"', '\\"')

def unescape_double_quote(string):
    quoting = False
    chars = []
    for c in string:
        if not quoting:
            if c == '\\':
                quoting = True
            else:
                chars.append(c)
        if quoting:
            chars.append(c)
            quoting = False
    return ''.join(chars)

class FlatPathType(object):
    """
    Types of path:
    ."hello"   :: prefix path
    ."hello".  :: type path <- indicates the type of an entry
    ."hello"[  :: type path <- indicates the type of an entry
    ."hello"=  :: value path
    """


class PrefixPath(FlatPathType):
    """A path like that just indicates the name of something, these do not exist in our store. e.g

    ."hello"     or
    ."hello"[0]
    """

class DictPrefixPath(PrefixPath):
    """A prefix path whose parent is a dictionary. e.g.

    ."hello"

    """

class ListPrefixPath(PrefixPath):
    """A prefix path whose parent is a list. e.g.
    ."hello"[0]
    """

class TypePath(FlatPathType):
    """A path that indicates data type. e.g.

    ."hello"[   or
    ."hello".   or

    """

class DictPath(TypePath):
    """A path that indicates this key maps to dict. e.g.

    ."hello".

    """

class ListPath(TypePath):
    """A path that indicates this key maps to a list. e.g.

    ."hello"[

    """

class ValuePath(TypePath):
    """A path that indicates this key maps to a simple value (boolean, string or float) e.g.

    ."hello"."world"=

    """

class LengthPath(TypePath):
    """A path that tells us how long an iterable is

    ."hello"."world"#

    """



class IncorrectType(Exception):
    def __init__(self, prefix, got_type, wanted_type):
        Exception.__init__(self)
        self.prefix = prefix
        self.got_type = got_type
        self.wanted_type = wanted_type

    def __str__(self):
        return '{!r}: Wanted {} got {}'.format(self.prefix, self.wanted_type, self.got_type)

class RootNode(Exception):
    "Operation is not supported for the root node"

class PathCorrupt(Exception):
    "This path looks broken"
    def __init__(self, path):
        Exception.__init__(self)
        self.path = path

    def __str__(self):
        print 'Path is corrupt {!r}'.format(self.path)

DICT_PATH, LIST_PATH, VALUE_PATH, LENGTH_PATH, LIST_PREFIX_PATH, DICT_PREFIX_PATH = (
    DictPath(), ListPath(), ValuePath(), LengthPath(), ListPrefixPath(), DictPrefixPath())

class FlatPath(object):
    # Nope: I'm not fully parsing this
    #   this would have the advantage of effectively adding assertions everywhere
    #   and potentially making code a lot easier to understand
    def __init__(self, prefix):
        self._prefix = prefix
        self._path_type = None
        self._key_string = None

    def __repr__(self):
        return '<FlatPath prefix={}>'.format(self._prefix)

    def __eq__(self, other):
        return self.key() == other.key()

    def list_key(self):
        return self._prefix + "["

    def path_type(self):
        if self._path_type is None:
            self._path_type = self._get_path_type()

        return self._path_type

    def _get_path_type(self):
        if self._prefix == '':
            return DICT_PREFIX_PATH
        elif self._prefix[-1] == '.':
            return DICT_PATH
        elif self._prefix[-1] == '[':
            return LIST_PATH
        elif self._prefix[-1] == '=':
            return VALUE_PATH
        elif self._prefix[-1] == '#':
            return LENGTH_PATH
        elif self._prefix[-1] == ']':
            return LIST_PREFIX_PATH
        elif self._prefix[-1] == '"':
            return DICT_PREFIX_PATH
        else:
            raise PathCorrupt(self._prefix)

    def depth(self):
        depth = 0
        path = self
        while True:
            path = path.prefix()
            if path.key() == '':
                return depth
            else:
                depth += 1
            path = path.parent()

    def ensure_type(self, Type):
        if not isinstance(self.path_type(), Type):
            raise IncorrectType(self._prefix, self.path_type(), Type)

    def dict(self):
        # We could do this though having different
        #  types. But I think it might make debugging
        #   slightly difficult
        self.ensure_type(PrefixPath)
        return FlatPath(self._prefix + '.')

    def list(self):
        self.ensure_type(PrefixPath)
        return FlatPath(self._prefix + '[')

    def key_string(self):
        if self._key_string is None:
            self._key_string = self._get_key_string()

        return self._key_string

    def _get_key_string(self):
        self.ensure_type(DictPrefixPath)
        _, string  = self._remove_terminal_string(self.prefix().key())
        return string

    def index_number(self):
        self.ensure_type(ListPrefixPath)
        prefix = self._remove(self._prefix, ']')
        prefix, integer_string = self._remove_terminal_integer(prefix)
        self._remove(prefix, '[')
        return int(integer_string)

    def parent(self):
        # Yes we could do this with a parser
        if isinstance(self.path_type(), ListPrefixPath):
            prefix = self._remove(self._prefix, ']')
            prefix, _ = self._remove_terminal_integer(prefix)
            prefix = self._remove(prefix, '[')
            return FlatPath(prefix)
        elif isinstance(self.path_type(), DictPrefixPath):
            if self._prefix == '':
                raise RootNode()
            prefix, _  = self._remove_terminal_string(self._prefix)
            prefix = self._remove(prefix, '.')
            return FlatPath(prefix)
        else:
            raise IncorrectType(self._prefix, self.path_type(), TypePath)

    @staticmethod
    def _remove_terminal_integer(string):
        integer_string = []
        while True:
            if string[-1] in "0123456789":
                integer_string.append(string[-1])
                string = string[:-1]
            else:
                break
        return string, ''.join(reversed(integer_string))

    @classmethod
    def _remove_terminal_string(cls, string):
        initial_string = string

        if string[-1] != '"':
            raise ValueError(string)

        string = string[:-1]
        state = None
        QUOTE = 'quote'
        while True:
            # We can if things like \ \ "
            if state == None:
                if string[-1] == '"':
                    state = QUOTE
                    string = string[:-1]
                else:
                    string = string[:-1]
            elif state == QUOTE:
                if string[-1] == '\\':
                    state = None
                    string = string[:-1]
                else:
                    break
            else:
                raise ValueError(state)

        end = unescape_double_quote(initial_string[len(string) + 1:-1])
        return string, end

    @staticmethod
    def _remove(string, char):
        if string[-1] == char:
            return string[:-1]
        else:
            raise ValueError(string[-1])

    def lookup(self, key):
        self.ensure_type(DictPath)
        return FlatPath(self._prefix + '"{}"'.format(escape_double_quote(key)))

    def length(self):
        self.ensure_type(PrefixPath)
        return FlatPath(self._prefix + '#')

    def index(self, index):
        self.ensure_type(ListPath)

        if not isinstance(index, int):
            raise ValueError(index)

        return FlatPath(self._prefix + '{}]'.format(index))

    def value(self):
        """A path representing the value of a particular prefix"""
        # e.g ."hello"[0] -> ."hello"[0]=
        self.ensure_type(PrefixPath)
        return FlatPath(self._prefix + '=')

    def key(self):
        return self._prefix

    def prefix(self):
        if isinstance(self.path_type(), (ValuePath, TypePath)):
            return FlatPath(self._prefix[:-1])
        elif isinstance(self.path_type(), PrefixPath):
            return self
        else:
            raise ValueError(self._prefix)

