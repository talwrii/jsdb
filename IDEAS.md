# bsddb

I'm not sure about berkleydb:

- It's seems kind of bad at IPC (I had to close and re-open files to get things to sync)
- We have this weird but in set_location

Alternatives to berkley db. All we really need is a range query.

   http://stackoverflow.com/questions/260804/alternative-to-berkeleydb/25200802#25200802

**sophia** looks good but isn't in debian (we could just build and bunlde this ourselves).
**leveldb** is in debian. It explicitly monster bars IPC though...

## I've been able to corrupt bsddb before

`bsddb` seems to get into a state where there is a key that I can neither read not delete. I think this might be to do
with shutting down / switching off a machine while something is happening (since this tends to happen after a restart).
When this has happened I've worked aroudn this by copying all the keys apart from the affected one.

Example traceback:

```
Traceback (most recent call last):
  File "<console>", line 2, in <module>
  File "/usr/lib/python2.7/bsddb/__init__.py", line 270, in __getitem__
    return _DeadlockWrap(lambda: self.db[key])  # self.db[key]
  File "/usr/lib/python2.7/bsddb/dbutils.py", line 68, in DeadlockWrap
    return function(*_args, **_kwargs)
  File "/usr/lib/python2.7/bsddb/__init__.py", line 270, in <lambda>
    return _DeadlockWrap(lambda: self.db[key])  # self.db[key]
KeyError: '."metrics"."keypresses.hourly"."values"[14]."time"='
>
```



