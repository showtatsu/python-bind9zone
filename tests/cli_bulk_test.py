import sys
import re
import pytest
import os
from itertools import zip_longest
from contextlib import contextmanager
from io import StringIO

from bind9zone.cli import Bind9ZoneCLI

ZONEDIR_SRC = 'tests/input'
ZONEDIR = 'tests/output'


def get_connection_fixture_params():
    if os.getenv('TEST_POSTGRES'):
        return ['sqlite:///tests/db.sqlite3',
                'postgresql://postgres:postgres@db/database']
    else:
        return ['sqlite:///tests/db.sqlite3']


@contextmanager
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err


#@pytest.fixture(params=get_connection_fixture_params())
#def connection(request):
#    connection = request.param
#    con = ['--connection', connection]
#    Bind9ZoneCLI(['init', *con, '--drop']).run()
#    Bind9ZoneCLI(['bulkpush', *con,
#                  '--dir', ZONEDIR_SRC,
#                  '--zones', 'public/example.com,private/example.com'
#                  ]).run()
#    if not os.path.isdir(os.path.join(ZONEDIR, 'public')):
#        os.mkdir(os.path.join(ZONEDIR, 'public'))
#    if not os.path.isdir(os.path.join(ZONEDIR, 'private')):
#        os.mkdir(os.path.join(ZONEDIR, 'private'))
#    output_files = [
#        'public/example.com.zone',
#        'private/example.com.zone']
#    for f in output_files:
#        filepath = os.path.join(ZONEDIR, f)
#        if os.path.isfile(filepath):
#            os.remove(filepath)
#    return connection


def normalize_zonefile(stream):
    lines = [re.sub(r' *; .*$', '', line.strip()) for line in stream]
    lines = [s for s in filter(lambda s: s != '', lines)]
    return lines


def zonefile_is_same(a, b):
    with open(a, mode='r') as reader:
        a_lines = normalize_zonefile(reader)
    with open(b, mode='r') as reader:
        b_lines = normalize_zonefile(reader)
    return all([o == e for o, e in zip_longest(sorted(a_lines), sorted(b_lines))])


def test_bulkpull(connection):
    con = ['--connection', connection]
    zone = ['--zones', 'public/example.com,private/example.com']
    dirs = ['--dir', ZONEDIR]

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['bulkpull', *con, *zone, *dirs, '--mkdir']).run()
    assert code == 0

    assert zonefile_is_same(
        os.path.join(ZONEDIR_SRC, 'public/example.com.zone'),
        os.path.join(ZONEDIR, 'public/example.com.zone'),
    )
    assert zonefile_is_same(
        os.path.join(ZONEDIR_SRC, 'private/example.com.zone'),
        os.path.join(ZONEDIR, 'private/example.com.zone'),
    )


def test_pullzone(connection):
    con = ['--connection', connection]
    zone = ['--zone', 'public/example.com']

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['pullzone', *con, *zone]).run()
    assert code == 0

    output = normalize_zonefile(out.getvalue().strip().split('\n'))
    with open(os.path.join(ZONEDIR_SRC, 'public/example.com.zone'), mode='r') as reader:
        src_lines = normalize_zonefile(reader)

    return all([o == e for o, e in zip_longest(sorted(src_lines), sorted(output))])


def test_delete_and_pushzone(connection):
    con = ['--connection', connection]
    zone = ['--zone', 'public/example.com']
    dirs = ['--dir', ZONEDIR]

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['deletezone', *con, *zone]).run()
    assert code == 0

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['pullzone', *con, *zone]).run()
    assert code == 2
    output = normalize_zonefile(out.getvalue().strip().split('\n'))
    expect = ['']
    return all([o == e for o, e in zip_longest(sorted(expect), sorted(output))])

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['pushzone', *con, *zone, *dirs]).run()
    assert code == 0

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['pullzone', *con, *zone, *dirs]).run()
    assert code == 0
    output = normalize_zonefile(out.getvalue().strip().split('\n'))
    with open(os.path.join(ZONEDIR_SRC, 'public/example.com.zone'), mode='r') as reader:
        expect = normalize_zonefile(reader)
    return all([o == e for o, e in zip_longest(sorted(expect), sorted(output))])
