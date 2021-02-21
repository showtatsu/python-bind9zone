import pytest
from io import StringIO
from bind9zone import ZoneRecord, ZoneFile


@pytest.fixture
def records():
    zonefile = 'tests/input/public/example.com.zone'
    with open(zonefile, mode='r') as reader:
        stream = StringIO(reader.read())
    records = [ZoneRecord({**r, "namespace": "public"})
               for r in ZoneFile.from_stream(stream)]
    return records


def test_attributes_modifier(records):
    record = [r for r in records if r.name == 'edit1' and r.type == 'A'][0]
    assert record.name == 'edit1'
    assert record.origin == 'example.com.'
    assert record.type == 'A'
    assert record.namespace == 'public'
    assert record.ttl == 60
    assert record.data == '192.0.2.201'
    assert record.fqdn == 'edit1.example.com'
    assert record.get_fqdn() == 'edit1.example.com'

    expect = ZoneRecord(record.to_dict())
    assert record.compare(expect)

    record.ttl = '3M'
    assert record.ttl == 60 * 3
    record.ttl = '3H'
    assert record.ttl == 60 * 60 * 3
    record.ttl = '3D'
    assert record.ttl == 60 * 60 * 24 * 3
    record.ttl = '3W'
    assert record.ttl == 60 * 60 * 24 * 7 * 3


def test_attributes_modifier_exceptions(records):
    record = [r for r in records if r.name == 'edit2' and r.type == 'A'][0]
    assert record.name == 'edit2'
    assert record.origin == 'example.com.'
    assert record.type == 'A'
    assert record.namespace == 'public'
    assert record.ttl == 60
    assert record.data == '192.0.2.202'
    assert record.fqdn == 'edit2.example.com'
    assert record.get_fqdn() == 'edit2.example.com'

    with pytest.raises(ValueError):
        record.origin = 'example.com'
    with pytest.raises(ValueError):
        record.ttl = '3X'
    with pytest.raises(ValueError):
        record.name = None
    with pytest.raises(ValueError):
        record.origin = None
    with pytest.raises(ValueError):
        record.data = None
    with pytest.raises(ValueError):
        record.namespace = 'invalid namespace'
    with pytest.raises(ValueError):
        record.compare('invalid compare')
    with pytest.raises(ValueError):
        record.compare('invalid compare')


def test_attributes_modifier_omit():
    record = ZoneRecord({
        'name': 'mock.example.com.',
        'type': 'A',
        'data': '192.0.2.201',
        'ttl': 60,
        'origin': 'example.jp.',
        'namespace': 'public'
    })
    # nameがFQDNで適切なorigin配下に存在していない場合、nameはFQDN形式で維持されます。
    assert record.name == 'mock.example.com.'
    assert record.origin == 'example.jp.'
    assert record.fqdn == 'mock.example.com'
    assert record.get_fqdn() == 'mock.example.com'
