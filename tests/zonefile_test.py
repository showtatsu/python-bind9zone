import re
import os
import textwrap
from io import StringIO
from bind9zone import ZoneFile, ZoneRecord


def normalize_zonefile(stream):
    lines = [re.sub(r' *; .*$', '', line.strip()) for line in stream]
    lines = [s for s in filter(lambda s: s != '', lines)]
    return lines


def test_zonefile_io(zonedir_src):
    zonefile = os.path.join(zonedir_src, 'private/example.com.zone')
    with open(zonefile, mode='r') as reader:
        stream = StringIO(reader.read())
    records = [ZoneRecord(r) for r in ZoneFile.from_stream(stream)]
    zonetext = ZoneFile.to_zonefile(records)
    expect = re.sub(r'^\s+', '', textwrap.dedent("""\
    $ORIGIN example.com.
    $TTL 600
    @  IN SOA ns.example.com. admin.example.com. ( 2101202346 600 600 604800 60 ) ; meta=(id=None)
    @ 60 IN A 192.168.1.11 ; meta=(id=None)
    @ 60 IN MX 10 server ; meta=(id=None)
    @ 60 IN NS dns ; meta=(id=None)
    @ 60 IN TXT "v=spf1 ip4:192.168.1.5/32 ~all" ; meta=(id=None)
    alias 60 IN CNAME server ; meta=(id=None)
    dns 60 IN A 192.168.1.11 ; meta=(id=None)
    edit1 60 IN A 192.168.1.201 ; meta=(id=None)
    edit2 60 IN A 192.168.1.202 ; meta=(id=None)
    edit3 60 IN A 192.168.1.203 ; meta=(id=None)
    fqdn1 60 IN CNAME server.example.com. ; meta=(id=None)
    fqdn2 60 IN CNAME www.example.jp. ; meta=(id=None)
    mixed 60 IN A 192.168.2.13 ; meta=(id=None)
    mixed 60 IN AAAA 2001:0DB8::1 ; meta=(id=None)
    mixed 60 IN TXT "mixed-server" ; meta=(id=None)
    multi 60 IN A 192.168.2.10 ; meta=(id=None)
    multi 60 IN A 192.168.2.11 ; meta=(id=None)
    multi 60 IN A 192.168.2.12 ; meta=(id=None)
    server 60 IN A 192.168.1.5 ; meta=(id=None)
    space 60 IN TXT "private" ; meta=(id=None)
    """).strip())
    assert zonetext == expect


def test_zonefile_syntaxtest(zonedir_src):
    zonefile = os.path.join(zonedir_src, 'private/example.jp.zone')
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
