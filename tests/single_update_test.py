import sys, re, itertools, time, os
import pytest
from io import StringIO
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from bind9zone import ZoneRecord, ZoneFile
from bind9zone.cli import Bind9ZoneCLI
from bind9zone import query


def test_set_records(session_factory):
    session = session_factory()

    records = query.get_records(session,
        namespace='public', origin='example.com.', name='edit3', type='A')
    assert [r.data for r in records] == ['192.0.2.203']
    for r in records:
        print(" before * {} {} m={} c={}".format(r.name, r.type, r.modified_at, r.created_at))
    session.close()

    time.sleep(3)

    session = session_factory()
    query.set_records(session,
        namespace='public', origin='example.com.', name='edit3', type='A', data='192.0.2.1')

    records = query.get_records(session,
        namespace='public', origin='example.com.')
    for r in records:
        print(" after  * {} {} m={} c={}".format(r.name, r.type, r.modified_at, r.created_at))
    session.close()
