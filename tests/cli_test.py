import sys
import re
import itertools
from contextlib import contextmanager
from io import StringIO

from bind9zone.cli import Bind9ZoneCLI


@contextmanager
def captured_output():
    new_out, new_err = StringIO(), StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = new_out, new_err
        yield sys.stdout, sys.stderr
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def normalize_zonefile(stream):
    lines = [re.sub(r' *; .*$', '', line.strip()) for line in stream]
    lines = [s for s in filter(lambda s: s != '', lines)]
    return lines


def zonefile_is_same(a, b):
    with open(a, mode='r') as reader:
        a_lines = normalize_zonefile(reader)
    with open(b, mode='r') as reader:
        b_lines = normalize_zonefile(reader)
    return all([o == e for o, e in itertools.zip_longest(sorted(a_lines), sorted(b_lines))])


def test_get_record(connection):
    con = ['--connection', connection]
    zone = ['--zone', 'public/example.com']

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'server', 'A']).run()
    assert code == 0
    
    output = normalize_zonefile(out.getvalue().strip().split('\n'))
    expect = ['server 60 IN A 192.0.2.11']
    if not output or output == [""]:
        RuntimeError("stfout capture failed")
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])


def test_get_multirecord(connection):
    con = ['--connection', connection]
    zone = ['--zone', 'public/example.com']

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'multi', 'A']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    expect = ['multi 60 IN A 192.0.2.20',
              'multi 60 IN A 192.0.2.21', 'multi 60 IN A 192.0.2.22']
    assert code == 0
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])


def test_get_mixedrecord(connection):
    con = ['--connection', connection]
    zone = ['--zone', 'public/example.com']

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'mixed']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    expect = ['mixed 60 IN A 192.0.2.33', 'mixed 60 IN AAAA 2001:0DB8::2:1',
              'mixed 60 IN TXT "mixed-server-public"']
    assert code == 0
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])


def test_get_nxrecord(connection):
    con = ['--connection', connection]
    zone = ['--zone', 'public/example.com']

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'nxdomain', 'A']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    expect = ['']
    assert code == 2
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])


def test_set_record(connection):
    con = ['--connection', connection]
    zone = ['--zone', 'public/example.com']

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'edit1', 'A']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    expect = ['edit1 60 IN A 192.0.2.201']
    assert code == 0
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(
            ['set', *con, *zone, 'edit1', 'A', '192.0.2.251']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    assert code == 0

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'edit1', 'A']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    expect = ['edit1 60 IN A 192.0.2.251']
    assert code == 0
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])


def test_set_multirecord(connection):
    con = ['--connection', connection]
    zone = ['--zone', 'public/example.com']

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'edit2', 'A']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    expect = ['edit2 60 IN A 192.0.2.202']
    assert code == 0
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['set', *con, *zone, 'edit2',
                             'A', '192.0.2.242', '192.0.2.252']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    assert code == 0

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'edit2', 'A']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    expect = ['edit2 60 IN A 192.0.2.242', 'edit2 60 IN A 192.0.2.252']
    assert code == 0
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])


def test_set_mixedrecord(connection):
    con = ['--connection', connection]
    zone = ['--zone', 'public/example.com']

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'edit3']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    expect = ['edit3 60 IN A 192.0.2.203']
    assert code == 0
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(
            ['set', *con, *zone, 'edit3', 'A', '192.0.2.253']).run()
        code = Bind9ZoneCLI(['set', *con, *zone, 'edit3',
                             'AAAA', '2001:0DB8::3:1']).run()
        code = Bind9ZoneCLI(
            ['set', *con, *zone, 'edit3', 'TXT', 'public']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    assert code == 0

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'edit3']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    expect = ['edit3 60 IN A 192.0.2.253',
              'edit3 60 IN AAAA 2001:0DB8::3:1', 'edit3 60 IN TXT public']
    assert code == 0
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(
            ['set', *con, *zone, 'edit3', 'CNAME', 'server']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    assert code == 0

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'edit3']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    expect = ['edit3 60 IN CNAME server']
    assert code == 0
    print(output)
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])


def test_delete_multirecord(connection):
    con = ['--connection', connection]
    zone = ['--zone', 'private/example.com']

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'multi']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    expect = ['multi 60 IN A 192.168.2.10',
              'multi 60 IN A 192.168.2.11', 'multi 60 IN A 192.168.2.12']
    assert code == 0
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['delete', *con, *zone, 'multi', 'A']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    assert code == 0

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'multi']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    expect = ['']
    assert code == 2
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])


def test_delete_mixedrecord(connection):
    con = ['--connection', connection]
    zone = ['--zone', 'private/example.com']

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'mixed']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    expect = ['mixed 60 IN A 192.168.2.13',
              'mixed 60 IN AAAA 2001:0DB8::1', 'mixed 60 IN TXT "mixed-server"']
    assert code == 0
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['delete', *con, *zone, 'mixed', 'A']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    assert code == 0

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'mixed']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    expect = ['mixed 60 IN AAAA 2001:0DB8::1',
              'mixed 60 IN TXT "mixed-server"']
    assert code == 0
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['delete', *con, *zone, 'mixed']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    assert code == 0

    with captured_output() as (out, err):
        code = Bind9ZoneCLI(['get', *con, *zone, 'mixed']).run()
    output = [re.sub(r'\s*; .+$', '', s)
              for s in out.getvalue().strip().split('\n')]
    expect = ['']
    assert code == 2
    assert all([o == e for o, e in itertools.zip_longest(
        sorted(output), sorted(expect))])
