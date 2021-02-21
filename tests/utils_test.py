import sys, re, itertools, time, pytest
from contextlib import contextmanager
from io import StringIO
from bind9zone import utils as zutils


def test_create_default_soa_params():
    rec = zutils.create_default_soa_params()
    expect = {'serial':1, 'refresh':3600, 'retry':1200, 'expire':604800, 'minimum':600}
    assert all([rec[k] == expect[k] for k in (set(rec.keys()) | set(expect.keys()))])


def test_email_to_rname():
    emails = {
        'username@example.com': 'username.example.com.',
        'username@example.co.jp': 'username.example.co.jp.',
        'username@example.co.jp.': 'username.example.co.jp.',
        'user.name@example.com': 'user\\.name.example.com.',
    }
    assert all([zutils.email_to_rname(k) == v for k, v in emails.items()])


def test_origin_with_dot():
    origins = {
        'example.com': 'example.com.',
        'example.com.': 'example.com.',
        'example.co.jp': 'example.co.jp.',
        'example.co.jp.': 'example.co.jp.',
    }
    assert all([zutils.origin_with_dot(k) == v for k, v in origins.items()])

    origins = ['.example.com', ' example.com', '..example.com']
    for o in origins:
        with pytest.raises(ValueError):
            zutils.origin_with_dot(o)
