# jsdb

A moderately efficient, pure-python, single-user, JSON, persistent, object-graph database.

## Contraindications

You may well not want to use this library:

- For a general purpose, multi-user data store which allows data to be used in a number of ways, you might like to use a DBMS like **Postgres** with or without an ORM
- If you want something small and in-process then you might like to use **sqlite**, again with or without an ORM
- If you want to store schema-less records, you might consider a document store like **MongoDB**, **CouchDB** or **ElasticSearch**
- If you want something very easy to call from **Python**, you might want to use something like `shelve` (if you aren't concerned about nesting), or just use `pickle` or `json` directly (if your data is small)
- Even if you need an object-graph, you might want to use `zodb` (a relatively battle-tested object-graph used with **Zope**)

This library has only just been written, you probably want to be careful when giving it important data.

## Motivation

> Just persist this data for me and do it efficiently:  I don't care about indexes; I don't want to start any processes; I don't want to think about schemas. Yes, I know all the things that these tools would give me, and I don't need them!

There are a number of simple tools where the overhead of running storage processes or defining schemas can feel excessive. For example, small command line tools that need to "just work" or simple games.

Often, a simple key-value store does not provide quite enough structure for these tools but *JSON* does.

This library provides a json-like data store, which is very easy to use, an algorithmically efficient (i.e. not **O(N)** for every operation!).

## Installing

```sh
python setup.py install
virtualenv env; env/bin/pip install .
```

## Using

```python
>>> import jsdb
>>> db = jsdb.Jsdb('/tmp/file.jsdb')
>>> db['toplevel'] = 1
>>> db['nested'] = dict(a=1)
>>> db['nested']['b'] = 1
>>> db.commit()

>>> with db:
...     db['toplevel'] = 2
...
>>>
```

## Developing

```sh
python setup.py develop
nose -m tests
```

## Implementation details

We flatten down a dicts nested structure to a single string-to-string mapping structure. Roughly, the entry at `d["a"]["b"]["c"][0][1]` is stored at a key `a.b.c[0][1]=`. This string-to-string mapping is persisted in a b-tree (`bsddb`).

We make use the b-tree's ordered key structure to make partial iteration moderately efficient.

A layer rollback and object serialization is added on top of this.

## Performance

Looking up a value is **O(log N)**.

Iterating a substructure (dictionary or list) of length **S** is **O(S log N)**, regardless of the substructure's depth.

Moving and copying a substructure will deep copy the substructure. Modifying a list in any way results in the entire list deep-copied, even if you are just appending entries; the same is not true for dictionary structures.

It would not be particularly difficult to make appending to a list more efficient, insertion intrinsically requires a deep-copy of
everything after the insertion point.

## Caveats

Some operations that might be cheap with python dictionaries can be expensive (see the discussion of performance).

Only JSON types can be stored, this is a design decision. It would not be too hard to layer your own pickling on top of this.

This library is new, be careful with it. That said, it *is* tested with some fairly aggressive fuzzing.

## Why not ZODB?

Before using this library you should consider `ZODB`; it fills the same role, while being more feature-complete and extensively used in production. However, it is not without flaws:

### `ZODB` has a kind of slow startup time

```sh
# time python -c "import jsdb.jsdb; jsdb.jsdb.Jsdb('/tmp/file')"
python -c "import jsdb.jsdb; jsdb.jsdb.Jsdb('/tmp/file')"###  0.03s user 0.00s system 95% cpu 0.029 total

# time python -c "import ZODB.FileStorage; ZODB.DB(ZODB.FileStorage.FileStorage('/tmp/file'))"
python -c   0.16s user 0.01s system 98% cpu 0.174 total
```

Now 0.16s isn't a very long time, until you want to, say, run you program 4 times in a one-liner in response to a key-press. At this point your keypress takes half a second.

### `ZODB` is kind of big

```sh
# wc -l $(find  /usr/lib/python2.7/dist-packages/ZODB -name '*.py') | grep total
  30679 total
```

This compares to around 2000 lines including tests for `jsdb`.
Small often means simple and easy to understand.

### `ZODB` is kind of clever; `jsdb` tries to be stupid

If you use `ZODB`, you may well end up peppering your code with `persistent.list.PersistentList` and `persistent.mapping.PersistentMapping`. `ZODB` will sometimes succeed in pickling things that aren't really picklable. Perhaps you'll make a mistake and `ZODB` won't commit your objects for you. `jsdb` is a little more stupid.

## Similar projects

- `dobbin` https://pypi.python.org/pypi/dobbin
- `ZODB` http://www.zodb.org/
- `jsondb` https://github.com/shaung/jsondb - a similar approach using an `sqlite` database
