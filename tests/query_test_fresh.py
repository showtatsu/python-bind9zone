"""
query.pyに対する編集を伴わないテスト項目です。
"""

from bind9zone import query


def test_get_records(session_factory):
    session = session_factory()
    records = query.get_records(session, namespace='public', origin='example.com.', name='server', type='A')
    assert [r.data for r in records] == ['192.0.2.11']


def test_get_namespace_zones(session_factory):
    session = session_factory()
    nsz = query.get_namespace_zones(session)
    expect = [('public', 'example.com.'), ('private', 'example.com.')]
    assert nsz == expect
