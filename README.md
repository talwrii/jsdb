# jsdb

A moderately efficient, pure-python, single-user, json, object-graph database.

## Contraindications

You may well not want to use this library:

- For a general purpose, multi-user data store which allows data to be used in a number of ways, you might like to use a DBMS like _Postgres_ with or without an ORM
- If you want something small and in-process then you might like to use _sqlite_, again with or without an ORM
- If you want to store schema-less records, you might consider a document store like _MongoDB_, _CouchDB_ or _ElasticSearch_
- If you want something very easy to call from _Python_, you might want to use something like `shelve` (if you aren't concerned about nesting), or just use `pickle` or `json` directly (if your data is small)
- Even if you need an object-graph, you might want to use `zodb` (a relatively battle-tested object-graph used with _Zope_)

## Motivation

*Just persist this data for me and do it efficiently: I don't care about indexes; I don't want to start any processes; I don't want to think about schemas. Yes, I know all the things that these tools would give me, and I don't need them!*

There are a number of simple tools where the overhead of running storage processes or defining schemas can feel excessive. For example, small command line tools that need to "just work" or simple games.

Often, a simple key value store does not provide quite enough structure for these tools but _JSON_ does.

This library provides a json-like data store, which is very easy to use, an algorithmically efficient (i.e. not $O(N)$ for every operation!).

## Using

```python
import jsdb
db = jsdb.Jsdb('/tmp/file.jsdb')
db['toplevel'] = 1
db['nested'] = dict(a=1)
db['nested']['b'] = 1
db.commit()

with db:
    db['toplevel'] = 2
```

## Implementation details

We flatten does the nested structure so that we have keys, which are kind of like `a.b.c[0][1]=`. We then store these in a persisted btree (`bsddb`) structure, and make uses of btrees efficient sorted searching to make find the children of a particular node cheap.

We then layer rollback and serialization on top of this.

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
