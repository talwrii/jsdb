I'm not sure about berkleydb:

- It's seems kind of bad at IPC (I had to close and re-open files to get things to sync)
- We have this weird but in set_location

Alternatives to berkley db. All we really need is a range query.

   http://stackoverflow.com/questions/260804/alternative-to-berkeleydb/25200802#25200802

**sophia** looks good but isn't in debian (we could just build and bunlde this ourselves).
**leveldb** is in debian. It explicitly monster bars IPC though...



-
