#!/usr/bin/python
import bsddb
import copy
import logging
import os
import random
import shutil
import tempfile
import time
import unittest

from jsdb import flatdict, jsdb, leveldict, python_copy, rollback
from testutils import FakeOrderedDict

LOGGER = logging.getLogger('jsdb.fuzztest')

class JsdbFuzzTest(unittest.TestCase):
    def setUp(self):
        self.direc = tempfile.mkdtemp()
        self._filename = os.path.join(self.direc, 'file.jsdb')
        self.maxDiff = 1300

    def test_flattening_dict_ordered(self):
        make_dict = lambda: flatdict.JsonFlatteningDict(FakeOrderedDict())
        self.assert_fuzz(make_dict)

    def test_flattening_dict_unordered(self):
        make_dict = lambda: flatdict.JsonFlatteningDict(dict())
        self.assert_fuzz(make_dict)

    def test_jsdb(self):
        make_dict = lambda: jsdb.Jsdb(self._filename)
        def clean_up():
            os.unlink(self._filename)
        self.assert_fuzz(make_dict, commit=True, clean_up=clean_up)

    def test_jsdb_leveldb(self):
        make_dict = lambda: jsdb.Jsdb(self._filename, storage_class=leveldict.LevelDict)
        def clean_up():
            shutil.rmtree(self._filename)
        self.assert_fuzz(make_dict, commit=True, clean_up=clean_up)

    def test_flattening_bsddb(self):
        make_dict = lambda: flatdict.JsonFlatteningDict(jsdb.JsonEncodeDict(bsddb.btopen(self._filename, 'w')))
        def clean_up():
            os.unlink(self._filename)
        self.assert_fuzz(make_dict, commit=False, clean_up=clean_up)

    def test_rollback(self):
        make_dict = lambda: rollback.RollbackDict(dict())
        # unique values because a rollback dict is *meant* to not
        #   clone nested structures
        self.assert_fuzz(make_dict, commit=True, unique_values=True)

    def test_rollback_no_commit(self):
        make_dict = lambda: rollback.RollbackDict(dict())
        self.assert_fuzz(make_dict, commit=False, unique_values=True)

    # def test_jsdb_performance(self):
    #     # This ends up being N**2, I think this due to deepcopy-ing
    #     #   hopeful this doesn't turn up if we consistently insert
    #     #   at the leaves (which is what we should see in normal
    #     #   operation)
    #     "Make sure that we can deal with big objects efficiently"
    #     # Switch off comparison after each comparison (since this starts with
    #     #   take up most of the time for big graphs)
    #     make_dict = lambda: jsdb.Jsdb(self._filename)
    #     def clean_up():
    #         os.unlink(self._filename)
    #     self.assert_fuzz(make_dict, commit=True, clean_up=clean_up, loops=1, operations=1000, check_comparison=False, log_every=100)

    def assert_fuzz(self, make_dict, commit=False, unique_values=False, clean_up=None, check_comparison=True, loops=3, operations=50, log_every=None):
        random.seed(0)
        for _ in xrange(loops):
            self.run_fuzzer(make_dict, operations, commit=commit, unique_values=unique_values, clean_up=clean_up,
                                check_comparison=check_comparison, log_every=log_every)

    def run_fuzzer(self, make_dict, iterations, commit, unique_values=False, clean_up=None, check_comparison=True, log_every=False):
        # uniq_values: created distinct values for the reference
        #    dictionary and our dictionary

        # to have confidence that this actually works
        #   we will perform random insertions and deletions
        #   and check that the structure matches a normal json options

        if not unique_values:
            value_func = lambda x: x
        else:
            value_func = copy.deepcopy

        json_dict = dict()
        db = make_dict()

        equivalent_code = [] # Make it easy to mess with code

        def log_operation(operation):
            equivalent_code.append(operation)

        start = time.time()

        try:
            for iteration in xrange(iterations):

                if log_every is not None:
                    if iteration % log_every == 0:
                        print iteration, time.time() - start

                paths = list(self.dict_insertion_path(json_dict))
                path = random.choice(paths)
                action = self.random_path_action(path)

                LOGGER.debug('Fuzz action %s %r', action, path)

                if action == 'dict-insert':
                    key = self.random_key()
                    value = self.random_value()
                    LOGGER.debug('Inserting %r -> %r', key, value)
                    log_operation('d{}[{!r}] = {!r}'.format(self.code_path(path), key, value))
                    self.lookup_path(db, path)[key] = value_func(value)
                    self.lookup_path(json_dict, path)[key] = value_func(value)
                elif action == 'list-insert':
                    value = self.random_value()
                    json_lst = self.lookup_path(json_dict, path)
                    db_list = self.lookup_path(db, path)
                    point = random.randint(0, len(json_lst))
                    LOGGER.debug('Inserting %r at %r', value, point)
                    log_operation('d{}.insert({!r}, {!r})'.format(self.code_path(path), point, value))
                    # pylint mis-detection
                    json_lst.insert(point, value_func(value)) # pylint: disable=no-member
                    db_list.insert(point, value_func(value))
                elif action == 'list-pop':
                    value = self.random_value()

                    log_operation('d{}.pop()'.format(self.code_path(path)))

                    lst = self.lookup_path(json_dict, path)
                    db_list = self.lookup_path(db, path)
                    if lst:
                        try:
                            lst.pop()
                        except IndexError:
                            pass

                        try:
                            db_list.pop()
                        except IndexError:
                            pass

                elif action == 'dict-modify':
                    value = self.random_value()

                    LOGGER.debug('Modifying %r -> %r', path, value)
                    log_operation('d{} = {!r}'.format(self.code_path(path), value))

                    self.set_path(db, path, value_func(value))
                    self.set_path(json_dict, path, value_func(value))
                elif action == 'list-modify':
                    value = self.random_value()

                    LOGGER.debug('Modifying %r -> %r', path, value)
                    log_operation('d{} = {!r}'.format(self.code_path(path), value))

                    self.set_path(db, path, value_func(value))
                    self.set_path(json_dict, path, value_func(value))

                elif action == 'dict-delete':
                    log_operation('del d{}'.format(self.code_path(path)))
                    self.set_path(json_dict, path, None, delete=True)
                    self.set_path(db, path, None, delete=True)
                elif action == 'list-del':
                    log_operation('del d{}'.format(self.code_path(path)))
                    self.set_path(db, path, None, delete=True)
                    self.set_path(json_dict, path, None, delete=True)
                else:
                    raise ValueError(action)

                if commit:
                    db.commit()

                # LOGGER.debug('%s', pprint.pformat(json_dict))
                if check_comparison:
                    self.assertEquals(python_copy.copy(db), json_dict)
        except:
            print '\n'.join(equivalent_code)
            print len(equivalent_code), 'Instructions'
            raise
        finally:
            if hasattr(db, 'close'):
                db.close()

        if clean_up:
            clean_up()


    def code_path(self, path):
        _, path = path
        return ''.join('[{!r}]'.format(part) for part in path)

    def random_key(self):
        key_length = 3
        length = random.randint(0, key_length)
        return ''.join([random.choice('abcdefghijklm') for _ in range(length)])

    def random_value(self):
        value_type = weighted_random_choice(dict(str=1, int=1, float=1, bool=1, dict=1, list=1, none=1))
        if value_type == 'str':
            return self.random_key()
        elif value_type == 'int':
            return random.randint(-1000, 1000)
        elif value_type == 'float':
            return (random.random() - 0.5) * 1000
        elif value_type == 'none':
            return None
        elif value_type == 'dict':
            return dict()
        elif value_type == 'list':
            return list()
        elif value_type == 'bool':
            return random.choice([True, False])
        else:
            raise ValueError(value_type)

    def random_path_action(self, (path_type, _raw_path)):
        if path_type == 'dict':
            return 'dict-insert'
        elif path_type == 'dict-key':
            return weighted_random_choice({
                'dict-modify': self.DICT_MODIFY_WEIGHT,
                'dict-delete': self.DICT_DEL_WEIGHT})
        elif path_type == 'list':
            return weighted_random_choice({
                'list-insert': self.DICT_MODIFY_WEIGHT,
                'list-pop': self.DICT_DEL_WEIGHT})
        elif path_type == 'list-item':
            return weighted_random_choice({
                'list-modify': self.DICT_MODIFY_WEIGHT,
                'list-del': self.DICT_DEL_WEIGHT})
        else:
            raise ValueError(path_type)

    DICT_MODIFY_WEIGHT = 5
    DICT_DEL_WEIGHT = 1

    def lookup_path(self, data, (_path_type, raw_path)):
        d = data
        for k in raw_path:
            d = d[k]
        return d

    def set_path(self, data, (_path_type, raw_path), value, delete=False):
        d = data
        for k in raw_path[:-1]:
            d = d[k]

        if delete:
            del d[raw_path[-1]]
        else:
            d[raw_path[-1]] = value

    @classmethod
    def dict_insertion_path(cls, d):
        yield ('dict', ())
        for k in d:
            if not isinstance(k, str):
                raise ValueError(k)
            if isinstance(d[k], dict):
                for descendant_path in cls.dict_insertion_path(d[k]):
                    action, path = descendant_path
                    yield action, (k,) + path
            elif isinstance(d[k], list):
                for descendant_path in cls.list_insertion_path(d[k]):
                    action, path = descendant_path
                    yield action, (k,) + path
            else:
                yield 'dict-key', (k,)

    @classmethod
    def list_insertion_path(cls, d):
        yield ('list', ())
        for i, v in enumerate(d):
            if isinstance(v, dict):
                for descendant_path in cls.dict_insertion_path(v):
                    action, path = descendant_path
                    yield action, (i,) + path
            elif isinstance(v, list):
                for descendant_path in cls.list_insertion_path(v):
                    action, path = descendant_path
                    yield action, (i,) + path
            else:
                yield 'list-item', (i,)


def weighted_random_choice(weights):
    rand = random.random() * sum(weights.values())
    total = 0
    for key in sorted(weights):
        total += weights[key]
        if rand <= total:
            return key
    else:
        raise Exception('Should never be reached')

if __name__ == '__main__':
    unittest.main()
