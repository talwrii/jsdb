Different backends (e.g leveldb) should produce different extensions. These should be recognised automatically by tools.
I caught a bug that didn't get caught by fuzzing, but was exhibited by closing and opening the dict. We should perhaps add this to fuzzing.
