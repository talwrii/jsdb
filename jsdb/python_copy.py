
import collections
import types

def copy(d):
    if isinstance(d, (int, unicode, str, float, bool, types.NoneType)):
        return d
    if isinstance(d, collections.Mapping):
        return {k:copy(v) for k, v in d.items()}
    elif isinstance(d, collections.Sequence):
        return [copy(v) for v in d]
    else:
        raise ValueError(d)
