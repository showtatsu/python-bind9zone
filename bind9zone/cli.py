import sys, os, re, io, time
import argparse
import itertools
import validators
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from .zonerecord import ZoneRecord
from .zonefile import ZoneFile

__version__ = '0.0.1'
__author__ = 'Tatsuya SHORIKI <show.tatsu.devel@gmail.com>'
__all__ = ["Bind9ZoneCLI"]


RRTYPE_LIST = ['A', 'AAAA', 'NS', 'CNAME', 'SOA', 'PTR', 'MX', 'TXT', 'SIG', 'KEY', 'SRV', 'KX', 'CERT']
class RTypeAction(argparse.Action):
    """ BIND9 RRTYPE (レコードタイプ)引数を受け取る argparse.Action です。
    """

    def __call__(self, parser, namespace, values, option_string=None):
        message = 'Specified resource type (rrtype) is not supported.'
        rrtype = values.upper()
        if rrtype not in rrtype_list:
            raise ValueError(message)
        setattr(namespace, self.dest, rrtype)


class MultiZonesAction(argparse.Action):
    """ 複数のzoneをコンマ(",")区切りで繋いだ引数を受け取る argparse.Action です。
    zoneは、"namespace/origin" の形式で表現されます。
    単一のzoneを受け取る場合はSingleZoneActionを使用します。
    """

    def __call__(self, parser, namespace, values, option_string=None):
        missing = 'Zone list required but not specified. Use ZONES environment or --zones option.'
        message = 'Zone format error. --zones option format must be "namespace/origin,...", "namespace/origin" or "origin"'
        if values is None or values == '':
            ValueError(missing)
        zones = [SingleZoneAction.parseValue(v, message) for v in values.split(',')]
        setattr(namespace, self.dest, zones)


class SingleZoneAction(argparse.Action):
    """ 単一のzone引数を受け取る argparse.Action です。
    zoneは、"namespace/origin" の形式で表現されます。
    複数のzoneを受け取る場合はMultiZonesActionを使用します。
    """

    def __call__(self, parser, namespace, values, option_string=None):
        message = 'Zone format error. --zone option must be in "namespace/origin" or "origin" format.'
        zone = SingleZoneAction.parseValue(values, message)
        setattr(namespace, self.dest, zone)

    @staticmethod
    def parseValue(values, message):
        info = values.split('/')
        if len(info) == 2:
            namespace, origin = info
        elif len(info) == 1:
            origin, = info
            namespace = None
        else:
            raise ValueError(message)
        try:
            validators.domain(re.sub(r'\.$', '', origin))
            if namespace is not None:
                validators.slug(namespace)
        except ValidateError:
            raise ValueError(message)
        return {"namespace":namespace, "origin": origin}


class Bind9ZoneCLI(object):
    """ bind9zone module のコマンドライン実行をサポートするクラスです。
    コマンドラインからDB上のzoneデータを修正したり、zonefileを出力したりできます。
    """

    def __init__(self, arguments=None):
        cls = self.__class__
        self.parser = cls.create_argparse()
        args = vars(self.parser.parse_args(args=arguments))
        if 'handler' in args:
            self.handler = args.pop('handler')
        else:
            self.handler = None
        self.args = args
    
    def run(self):
        if self.handler is None:
            self.parser.print_help()
            code = 1
        else:
            handler = self.handler
            code = handler(**self.args)
        return code

    @classmethod
    def create_argparse(cls):
        parser = argparse.ArgumentParser(prog='bind9zone',
            description='BIND9 zone record utils with database.')
        subparsers = parser.add_subparsers()

        # Options for init command
        subparser = subparsers.add_parser('init', help='see `init -h`')
        subparser.set_defaults(handler=cls.init)
        subparser.add_argument('-c', '--connection', action='store',
                                default=os.getenv('DB_CONNECT'),
                                help="Database connection string")
        subparser.add_argument('--drop', action='store_true')

        # Options for get command
        subparser = subparsers.add_parser('get', help='see `get -h`')
        subparser.set_defaults(handler=cls.getrecord)
        subparser.add_argument('-c', '--connection', action='store',
                                default=os.getenv('DB_CONNECT'),
                                help="Database connection string")
        subparser.add_argument('-z', '--zone', action=SingleZoneAction,
                                help='A Zone name to access, in namespace/origin format')
        subparser.add_argument('name',
                                help="Resource name.")
        subparser.add_argument('rtype', nargs='?', default=None, action='store',
                                choices=RRTYPE_LIST,
                                help="Resource type, like A, AAAA, TXT, etc.")

        # Options for delete command
        subparser = subparsers.add_parser('delete', help='see `delete -h`')
        subparser.set_defaults(handler=cls.deleterecord)
        subparser.add_argument('-c', '--connection', action='store',
                                default=os.getenv('DB_CONNECT'),
                                help="Database connection string")
        subparser.add_argument('-z', '--zone', action=SingleZoneAction,
                                help='A Zone name to access, in namespace/origin format')
        subparser.add_argument('name',
                                help="Resource name.")
        subparser.add_argument('rtype', nargs='?', default=None, action='store',
                                choices=RRTYPE_LIST,
                                help="Resource type, like A, AAAA, TXT, etc.")

        # Options for set command
        subparser = subparsers.add_parser('set', help='see `set -h`')
        subparser.set_defaults(handler=cls.setrecord)
        subparser.add_argument('-c', '--connection', action='store',
                                default=os.getenv('DB_CONNECT'),
                                help="Database connection string for pull")
        subparser.add_argument('-z', '--zone', action=SingleZoneAction,
                                help='A Zone name to access, in namespace/origin format')
        subparser.add_argument('name',
                                help="Resource name.")
        subparser.add_argument('rtype',
                                choices=RRTYPE_LIST,
                                help="Resource type, like A, AAAA, TXT, etc.")
        subparser.add_argument('values', nargs=argparse.REMAINDER,
                                help="Resource data.")

        # Options for pullzone command
        subparser = subparsers.add_parser('pullzone', help='see `pullzone -h`')
        subparser.add_argument('-c', '--connection', action='store',
                                default=os.getenv('DB_CONNECT'),
                                help="Database connection string for pull")
        subparser.add_argument('-z', '--zone', action=SingleZoneAction,
                                help='A Zone name to access, in namespace/origin format')
        subparser.add_argument('-d', '--dir', action='store', default=os.getenv('ZONEDIR'),
                                help="Directory for zone files")
        subparser.add_argument('--mkdir', action='store_true',
                                help='Make output namespace directories if not exists')
        subparser.set_defaults(handler=cls.pullzone)

        # Options for pushzone command
        subparser = subparsers.add_parser('pushzone', help='see `pushzone -h`')
        subparser.add_argument('-c', '--connection', action='store',
                                default=os.getenv('DB_CONNECT'),
                                help="Database connection string for pull")
        subparser.add_argument('-z', '--zone', action=SingleZoneAction,
                                help='A Zone name to access, in namespace/origin format')
        subparser.add_argument('-d', '--dir', action='store', default=os.getenv('ZONEDIR'),
                                help="Directory for zone files")
        subparser.set_defaults(handler=cls.pushzone)

        # Options for deletezone command
        subparser = subparsers.add_parser('deletezone', help='see `deletezone -h`')
        subparser.add_argument('-c', '--connection', action='store',
                                default=os.getenv('DB_CONNECT'),
                                help="Database connection string for delete")
        subparser.add_argument('-z', '--zones', action=MultiZonesAction,
                                help='Comma separated namespace/zone list')
        subparser.set_defaults(handler=cls.deletezone)

        # Options for bulkpull command
        subparser = subparsers.add_parser('bulkpull', help='see `bulkpull -h`')
        subparser.add_argument('-c', '--connection', action='store',
                                default=os.getenv('DB_CONNECT'),
                                help="Database connection string for pull")
        subparser.add_argument('-z', '--zones', action=MultiZonesAction,
                                default=os.getenv('ZONES'),
                                help='Comma separated namespace/zone list')
        subparser.add_argument('-d', '--dir', action='store', default=os.getenv('ZONEDIR'),
                                help="Directory for zone files")
        subparser.add_argument('--mkdir', action='store_true',
                                help='Make output namespace directories if not exists')
        subparser.set_defaults(handler=cls.bulkpull)

        # Options for bulkpush command
        subparser = subparsers.add_parser('bulkpush', help='see `bulkpush -h`')
        subparser.add_argument('-c', '--connection', action='store',
                                default=os.getenv('DB_CONNECT'),
                                help="Database connection string for push")
        subparser.add_argument('-z', '--zones', action=MultiZonesAction,
                                default=os.getenv('ZONES'),
                                help='Comma separated namespace/zone list')
        subparser.add_argument('-d', '--dir', action='store', default=os.getenv('ZONEDIR'),
                                help="Directory for zone files")
        subparser.set_defaults(handler=cls.bulkpush)

        return parser


    @staticmethod
    def getrecord(connection, zone, name, rtype):
        if connection is None:
            log_error(
                'Database connection string required but not specified. Use DB_CONNECT environment or --connection option.')
            return 1
        origin = zone['origin']
        namespace = zone['namespace']
        engine = create_engine(connection)
        session_factory = sessionmaker(bind=engine)
        Session = scoped_session(session_factory)
        records = ZoneRecord.get_record(Session, origin, namespace, name, rtype)
        if records is None or len(records) == 0:
            log_message('getrecord: No records founded. zone={} namespace={}, name={}, rtype={}', [
                        origin, namespace, name, rtype])
            return 2
        else:
            print('\n'.join([ZoneRecord(r).to_record(origin=origin) for r in records]))
            return 0


    @staticmethod
    def setrecord(connection, zone, name, rtype, values):
        if connection is None:
            log_error(
                'Database connection string required but not specified. Use DB_CONNECT environment or --connection option.')
            return 1
        origin = zone['origin']
        namespace = zone['namespace']
        engine = create_engine(connection)
        session_factory = sessionmaker(bind=engine)
        Session = scoped_session(session_factory)
        added, deleted = ZoneRecord.set_record(Session, origin, namespace, name, rtype, values, ttl=60)
        if deleted:
            log_message('\n'.join([' * DEL : ' + ZoneRecord(r).to_record(origin=origin) for r in deleted]))
        if added:
            log_message('\n'.join([' * SET : ' + ZoneRecord(r).to_record(origin=origin) for r in added]))
        return 0


    @staticmethod
    def deleterecord(connection, zone, name, rtype):
        if connection is None:
            log_error(
                'Database connection string required but not specified. Use DB_CONNECT environment or --connection option.')
            return 1
        origin = zone['origin']
        namespace = zone['namespace']
        engine = create_engine(connection)
        session_factory = sessionmaker(bind=engine)
        Session = scoped_session(session_factory)
        deleted = ZoneRecord.delete_record(Session, origin, namespace, name, rtype)
        if deleted:
            log_message('\n'.join([' * DEL : ' + ZoneRecord(r).to_record(origin=origin) for r in deleted]))
        return 0


    @staticmethod
    def pullzone(connection, zone, dir, mkdir):
        if connection is None:
            log_error(
                'Database connection string required but not specified. Use DB_CONNECT environment or --connection option.')
            return 1
        origin = zone['origin']
        namespace = zone['namespace']
        engine = create_engine(connection)
        session_factory = sessionmaker(bind=engine)
        Session = scoped_session(session_factory)
        return _pullzone(Session, dir, origin, namespace, mkdir)


    @staticmethod
    def pushzone(connection, zone, dir):
        if connection is None:
            log_error(
                'Database connection string required but not specified. Use DB_CONNECT environment or --connection option.')
            return 1
        if dir is None and sys.stdin.isatty():
            log_error('One of "zonefile directory" or "pipe zonefile into stdin" required, but not specified. Use ZONEDIR environment or --dir option, otherwise input a zonefile from stdin.')
            return 1
        origin = zone['origin']
        namespace = zone['namespace']
        engine = create_engine(connection)
        session_factory = sessionmaker(bind=engine)
        Session = scoped_session(session_factory)
        return _pushzone(Session, dir, origin, namespace)


    @staticmethod
    def bulkpull(connection, zones, dir, mkdir):
        if connection is None:
            log_error(
                'Database connection string required but not specified. Use DB_CONNECT environment or --connection option.')
            return 1
        if dir is None:
            log_error(
                'Zonefile directory required, but not specified. Use ZONEDIR environment or --dir option.')
            return 1
        engine = create_engine(connection)
        session_factory = sessionmaker(bind=engine)
        Session = scoped_session(session_factory)
        results = [_pullzone(Session, dir, zone['origin'], zone['namespace'], mkdir) for zone in zones]
        return max(results)


    @staticmethod
    def bulkpush(connection, zones, dir):
        if connection is None:
            log_error(
                'Database connection string required but not specified. Use DB_CONNECT environment or --connection option.')
            return 1
        if dir is None:
            log_error(
                'Zonefile directory required, but not specified. Use ZONEDIR environment or --dir option.')
            return 1
        engine = create_engine(connection)
        session_factory = sessionmaker(bind=engine)
        Session = scoped_session(session_factory)
        results = [_pushzone(Session, dir, z['origin'], z['namespace'])
                for z in zones]
        return max(results)


    @staticmethod
    def deletezone(connection, zones):
        if connection is None:
            log_error(
                'Database connection string required but not specified. Use DB_CONNECT environment or --connection option.')
            return 1
        engine = create_engine(connection)
        session_factory = sessionmaker(bind=engine)
        Session = scoped_session(session_factory)
        for zone in zones:
            origin = zone['origin']
            namespace = zone['namespace']
            count = ZoneRecord.delete_origin_from_database(Session, origin, namespace)
            if count == 0:
                log_message('DeleteZone: No records founded. zone={} namespace={}', [
                            origin, namespace])
            else:
                log_message('DeleteZone: completed. zone={} namespace={}, records={}', [
                            origin, namespace, count])
        return 0


    @staticmethod
    def init(connection, drop):
        engine = create_engine(connection)
        if engine.dialect.has_table(engine, ZoneRecord.__tablename__):
            if drop:
                ZoneRecord.__table__.drop(engine)
                log_message('Table {} dropped.', [ZoneRecord.__tablename__])
            else:
                log_error('Table {} already exists. To drop this table, use "--drop" option',
                        [ZoneRecord.__tablename__])
                return 3
        ZoneRecord.metadata.create_all(
            bind=engine, tables=[ZoneRecord.__table__], checkfirst=False)
        log_message('Table {} created.', [ZoneRecord.__tablename__])
        return 0

    #  ---- functions ----


def _pullzone(Session, target, origin, namespace, mkdir):
    records = ZoneRecord.from_database(Session, origin, namespace)
    if mkdir and target and not os.path.isdir(os.path.join(target, namespace)):
        os.mkdir(os.path.join(target, namespace))

    if records is None or len(records) == 0:
        log_message('Pullzone: No records founded. zone={} namespace={}', [
                    origin, namespace])
        return 2
    else:
        zonedata = ZoneFile.to_zonefile(records)
        _write_zone(zonedata, target=target,
                    origin=origin, namespace=namespace)
        log_message('Pullzone: completed. zone={} namespace={}, records={}', [
                    origin, namespace, len(records)])
        return 0


def _pushzone(Session, target, origin, namespace):
    zonedata = _read_zone(target, origin=origin, namespace=namespace)
    with io.StringIO(zonedata) as reader:
        records = [ZoneRecord({**r, 'namespace': namespace})
                for r in ZoneFile.from_stream(reader=reader, origin=origin)]
    if records is None or len(records) == 0:
        log_message('Pushzone: No records founded. zone={} namespace={}', [
                    origin, namespace])
        return 2
    session = Session()
    try:
        session.add_all(records)
        session.commit()
        log_message('Records pushed. zone={} namespace={} records={}', [
                    origin, namespace, len(records)])
    finally:
        session.close()
    return 0


def _read_zone(target=None, origin=None, namespace=None):
    if target is not None and target != '-':
        readpath = os.path.join(target, namespace, origin + '.zone')
        with open(readpath) as reader:
            content = reader.read()
            reader.close()
    else:
        content = sys.stdout.read()
    return content


def _write_zone(data, target=None, origin=None, namespace=None):
    if target is not None and target != '-':
        writepath = os.path.join(target, namespace, origin + '.zone')
        with open(writepath, mode='w') as output:
            print(data, file=output)
    else:
        print(data, file=sys.stdout)


def log_message(message, args=[], file=sys.stderr):
    if args:
        print(message.format(*args), file=file)
    else:
        print(message, file=file)


def log_error(message, args=[], file=sys.stderr):
    if args:
        print(message.format(*args), file=file)
    else:
        print(message, file=file)


def main():
    code = Bind9ZoneCLI().run()
    sys.exit(code)

if __name__ == '__main__':
    main()