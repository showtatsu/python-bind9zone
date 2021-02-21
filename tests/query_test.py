"""
query.pyに対する編集を伴うテスト項目です。
"""

import time
from bind9zone import query


def test_set_records(session_factory):
    session = session_factory()
    records = query.get_records(session,
                                namespace='public', origin='example.com.', name='edit1', type='A')
    assert [r.data for r in records] == ['192.0.2.201']

    query.set_records(session,
                      namespace='public', origin='example.com.', name='edit1', type='A', data='192.0.2.1')
    records = query.get_records(session,
                                namespace='public', origin='example.com.', name='edit1', type='A')
    assert [r.data for r in records] == ['192.0.2.1']

    query.set_records(session,
                      namespace='public', origin='example.com.', name='edit1', type='A', data=['192.0.2.1', '192.0.2.201'])
    records = query.get_records(session,
                                namespace='public', origin='example.com.', name='edit1', type='A')
    assert [r.data for r in records] == ['192.0.2.1', '192.0.2.201']

    query.delete_records(session,
                         namespace='public', origin='example.com.', name='edit1', type='A')
    records = query.get_records(session,
                                namespace='public', origin='example.com.', name='edit1', type='A')
    assert [r.data for r in records] == []


def test_set_soa_record(session_factory):
    session = session_factory()
    query.set_soa_records(session,
                          namespace='public', origin='first.example.com.',
                          nameserver='ns.example.com.', email='admin@example.com',
                          name='@', serial=20000000, refresh=3600, retry=1800, expire=10800, minimum=600, ttl=600)
    records = query.get_records(session,
                                namespace='public', origin='first.example.com.', name='@', type='SOA')
    assert [r.data for r in records] == [
        'ns.example.com. admin.example.com. ( 20000000 3600 1800 10800 600 )']

    query.set_soa_records(session,
                          namespace='public', origin='second.example.com.',
                          nameserver='ns.example.com.', email='admin.user@first.example.com')
    records = query.get_records(session,
                                namespace='public', origin='second.example.com.', name='@', type='SOA')
    assert [r.data for r in records] == [
        'ns.example.com. admin\\.user.first.example.com. ( 1 3600 1200 604800 600 )']

    query.set_soa_records(session,
                          namespace='private', origin='second.example.com',
                          nameserver='ns-private.example.com', email='zone.admin.user@first.example.com')
    records = query.get_records(session,
                                namespace='private', origin='second.example.com.', name='@', type='SOA')
    assert [r.data for r in records] == [
        'ns-private.example.com. zone\\.admin\\.user.first.example.com. ( 1 3600 1200 604800 600 )']
    records = query.get_records(session,
                                namespace='public', origin='second.example.com.', name='@', type='SOA')
    assert [r.data for r in records] == [
        'ns.example.com. admin\\.user.first.example.com. ( 1 3600 1200 604800 600 )']

    query.set_record(session, 'first.example.com.',
                     'public', 'test1', 'A', '192.0.2.1')
    query.set_record(session, 'first.example.com.',
                     'public', 'test2', 'A', '192.0.2.1')
    records = query.get_record(session, 'public', 'first.example.com.')
    assert len(records) == 3


def test_set_update_timestamp(session_factory):
    session = session_factory()

    records = query.get_records(session,
                                namespace='public', origin='example.com.', name='edit2', type='A')
    before_update = records[0].modified_at

    query.set_records(session,
                      namespace='public', origin='example.com.', name='edit2', type='A', data='192.0.2.1')

    records = query.get_records(session,
                                namespace='public', origin='example.com.', name='edit2', type='A')
    after_update = records[0].modified_at

    assert before_update < after_update


def test_update_serial(session_factory):
    session = session_factory()

    query.set_soa_records(session,
                          namespace='public', origin='third.example.com',
                          nameserver='ns.example.com', email='admin@example.com')

    records = query.get_records(session,
                                namespace='public', origin='third.example.com.',
                                name='@', type='SOA')
    assert [r.data for r in records] == [
        'ns.example.com. admin.example.com. ( 1 3600 1200 604800 600 )']

    time.sleep(0.1)

    # Auto update serial (may be updated)
    query.set_record(session, 'third.example.com.',
                     'public', 'test1', 'A', '192.0.2.1')
    query.update_serial(session, namespace='public',
                        origin='third.example.com.')
    records = query.get_records(session,
                                namespace='public', origin='third.example.com.', name='@', type='SOA')
    assert [r.data for r in records] == [
        'ns.example.com. admin.example.com. ( 2 3600 1200 604800 600 )']

    time.sleep(0.1)
    # Auto update serial (may be updated)
    query.set_record(session, 'third.example.com.',
                     'public', 'test2', 'A', '192.0.2.2')
    query.update_serial(session, namespace='public',
                        origin='third.example.com.')
    records = query.get_records(session,
                                namespace='public', origin='third.example.com.', name='@', type='SOA')
    assert [r.data for r in records] == [
        'ns.example.com. admin.example.com. ( 3 3600 1200 604800 600 )']

    time.sleep(0.1)
    # Auto update serial (may be updated)
    query.set_record(session, 'third.example.com.',
                     'public', 'test1', 'A', '192.0.2.11')
    query.update_serial(session, namespace='public',
                        origin='third.example.com.')
    records = query.get_records(session,
                                namespace='public', origin='third.example.com.', name='@', type='SOA')
    assert [r.data for r in records] == [
        'ns.example.com. admin.example.com. ( 4 3600 1200 604800 600 )']

    time.sleep(0.1)
    # Auto update serial (may NOT be updated)
    query.update_serial(session, namespace='public',
                        origin='third.example.com.')
    records = query.get_records(session,
                                namespace='public', origin='third.example.com.', name='@', type='SOA')
    assert [r.data for r in records] == [
        'ns.example.com. admin.example.com. ( 4 3600 1200 604800 600 )']

    # Manual update serial (updated)
    query.update_serial(session, namespace='public',
                        origin='third.example.com.', serial=100)
    records = query.get_records(session,
                                namespace='public', origin='third.example.com.', name='@', type='SOA')
    assert [r.data for r in records] == [
        'ns.example.com. admin.example.com. ( 100 3600 1200 604800 600 )']
