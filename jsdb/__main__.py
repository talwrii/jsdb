import argparse
import pprint

from . import leveldict

PARSER = argparse.ArgumentParser(description='Debug operations for jsdb')
PARSER.add_argument('--level', action='store_true', help='Use level db backend')
PARSERS = PARSER.add_subparsers(dest='command')
dump_under = PARSERS.add_parser('dump-under', help='Dump the keys of the underlying data store')
dump_under.add_argument('file', type=str)

args = PARSER.parse_args()

if args.level:
    Store = leveldict.LevelDict

if args.command == 'dump-under':
    store = Store(args.file)
    pprint.pprint(dict(store))
else:
    raise ValueError()
