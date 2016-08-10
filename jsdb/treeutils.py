
import bsddb

def key_after_func(store):
    """
    Get a function to find the key after a given string for
    a mapping
    """
    if hasattr(store, 'key_after_func'):
        return store.key_after_func()
    elif hasattr(store, 'key_after'):
        return store.key_after
    elif isinstance(store, bsddb._DBWithCursor): # pylint: disable=protected-access
        # There's no nice class without an _ that this is an
        #  instance of...
        def key_after(key):
            #   `set_location` sometimes lies about values
            #   being missing unless we call `first`
            #   first. I spent a while trying
            #   to turn this into a repro for bsddb
            #   but failed. This does not
            #   inspire confidence
            store.first()
            following_key = store.set_location(key)[0]
            if key == following_key:
                result = store.next()[0]
            else:
                result = following_key

            return result

        return key_after

    else:
        return None
