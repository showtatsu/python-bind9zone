import sys, re, itertools, time
from contextlib import contextmanager
from io import StringIO
from bind9zone import ZoneFile, ZoneRecord


def normalize_zonefile(stream):
    lines = [re.sub(r' *; .*$', '', line.strip()) for line in stream]
    lines = [s for s in filter(lambda s: s != '', lines)]
    return lines


def test_zonefile_io():
    zonefile = 'tests/input/private/example.com.zone'
    with open(zonefile, mode='r') as reader:
        stream = StringIO(reader.read())
    records = [ZoneRecord(r) for r in ZoneFile.from_stream(stream)]
    zonetext = '\n'.join([ZoneFile.to_zonefile(records) for r in records])


def test_zonefile_syntaxtest():
    zonefile = 'tests/input/private/example.jp.zone'
    with open(zonefile, mode='r') as reader:
        zonetext = reader.read()
    records = [ZoneRecord(r) for r in ZoneFile.from_stream(StringIO(zonetext))]

    r_opt_A = [r for r in records if r.name == 'opt' and r.type == 'A']
    r_opt_TXT = [r for r in records if r.name == 'opt' and r.type == 'TXT']
    r_opt_AAAA = [r for r in records if r.name == 'opt' and r.type == 'AAAA']

    assert len(r_opt_A) == 2
    assert len(r_opt_TXT) == 5
    assert len(r_opt_AAAA) == 1

    assert all([(r.ttl == 600) for r in r_opt_A])
    assert all([
        (r.ttl == 80 and r.data != '"opt-003"')
        or (r.ttl == 100 and r.data == '"opt-003"') for r in r_opt_TXT])
    assert all([(r.ttl == 600) for r in r_opt_AAAA])


def test_zonefile_multiline_soa():
    zonetext = '\n'.join([
        "$ORIGIN example.jp.",
        "$TTL 600",
        "@  IN SOA ns.example.com. admin.example.com. (",
        "    2101202346 600 600",
        "    604800 60 ; multi line soa",
        "); multi line soa",
    ])
    records = [ZoneRecord(r) for r in ZoneFile.from_stream(StringIO(zonetext))]
    assert records[0].name == '@'
    assert records[0].type == 'SOA'
