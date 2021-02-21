import re
import sys
import validators


def create_default_soa_params():
    return {'serial': 1, 'refresh': 3600, 'retry': 1200,
            'expire': 604800, 'minimum': 600}


def soa_parameters_to_data(mname, rname, serial, refresh, retry, expire, minimum):
    form = '{mname} {rname} ( {serial} {refresh} {retry} {expire} {minimum} )'
    updates = {
        'mname': mname, 'rname': rname,
        'serial': serial, 'refresh': refresh,
        'retry': retry, 'expire': expire, 'minimum': minimum
    }
    return form.format(**updates)


def soa_parameters_from_data(data):
    pattern = r'^(?:(?P<mname>[0-9A-Za-z.-]+)\s+)(?:(?P<rname>[0-9A-Za-z.\\-]+)\s+)\(\s*(?P<serial>[0-9]+)\s+(?P<refresh>[0-9]+)\s+(?P<retry>[0-9]+)\s+(?P<expire>[0-9]+)\s+(?P<minimum>[0-9]+)\s*\)$'
    match = re.match(pattern, data)
    if match:
        return match.groupdict()


def email_to_rname(email):
    """ Normalize email value into SOA's RNAME style.
    This method will convert "@" to "." and "." in user-parts to "\\.".
    """
    match = re.match(r'^(?P<user>[0-9A-Za-z.-]+)@(?P<domain>[0-9A-Za-z.-]+?)\.?$', email)
    if match:
        email_user = match.group('user').replace('.', '\\.')
        email_domain = match.group('domain')
        return email_user + '.' + email_domain + '.'
    else:
        raise ValueError('Invalid email specified.')


def origin_with_dot(origin, suffix=None, loose=True):
    """ Normalize "origin" value into FQDN with trailing dot(".")
    """
    if not origin.endswith('.'):
        if suffix:
            origin = origin + '.' + suffix
        elif not loose:
            raise ValueError('Origin "{}" is not FQDN and suffix not specified.'.format(origin))
    if not validators.domain(re.sub(r'\.$', '', origin)):
        raise ValueError('Invalid Origin Name, {}'.format(origin))
    return origin.rstrip('.') + '.'


def normalize_ttl(ttl):
    if ttl is None:
        return None
    elif str(ttl).isdigit():
        return int(ttl)
    else:
        m = re.match(r'^(?P<digit>[0-9]+)(?P<unit>[MHDW])$', ttl.upper())
        if m is not None:
            t = int(m.group('digit'))
            u = ({'M': 60, 'H': 3600, 'D': 86400, 'W': 604800})[
                m.group('unit')]
            return t * u
        else:
            raise ValueError('TTL must be a digit.')


def remove_zonefile_metadata(stream):
    lines = [re.sub(r' *; .*$', '', line.strip()) for line in stream]
    lines = [s for s in filter(lambda s: s != '', lines)]
    return lines


def output(message, args=[], file=None):
    text = message.format(*args) if args else message
    if file is None:
        print(text)
    else:
        print(text, file=file)


def log_message(message, args=[], file=sys.stderr):
    if args:
        print(message.format(*args), file=file)
    else:
        print(message, file=file)


def log_error(message, args=[], file=sys.stderr):
    if args:
        print(message.format(*args), file=file)
    else:
        print(message, file=file)
