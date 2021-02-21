import pytest, os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from bind9zone.cli import Bind9ZoneCLI

ZONEDIR_SRC = 'tests/input'
ZONEDIR = 'tests/output'


def get_connection_fixture_params():
    if os.getenv('TEST_POSTGRES'):
        return ['sqlite:///tests/db.sqlite3',
                'postgresql://postgres:postgres@db/database']
    else:
        return ['sqlite:///tests/db.sqlite3']


@pytest.fixture()
def zonedir_src():
    return ZONEDIR_SRC


@pytest.fixture()
def zonedir():
    return ZONEDIR


@pytest.fixture(scope='module', params=get_connection_fixture_params())
def connection(request):
    """ pytest対象モジュールの引数に"connection"を指定すると、
    このfixtureが実行され、データベースの初期化を行った上でconnection文字列を返します。
    1つのモジュール内(pyファイル)から複数回使用された場合でも、データベースの初期化処理が
    行われるのは各モジュールあたり最初の一回だけです。
    """
    connection = request.param
    con = ['--connection', connection]
    Bind9ZoneCLI(['init', *con, '--drop']).run()
    Bind9ZoneCLI(['bulkpush', *con,
                  '--dir', ZONEDIR_SRC,
                  '--zones', 'public/example.com,private/example.com'
                ]).run()
    return connection


@pytest.fixture(scope='function')
def session_factory(connection):
    """ pytest対象モジュールの引数に"session_factory"を指定すると、
    このfixtureが実行され、データベースの初期化を行った上でSQLAlchemyのscoped_sessionを返します。
    1つのモジュール内(pyファイル)から複数回使用された場合でも、データベースの初期化処理が行われるのは
    各モジュールあたり最初の一回だけです。
    """
    engine = create_engine(connection)
    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)
    return Session

