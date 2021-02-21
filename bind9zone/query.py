import itertools
import validators
from sqlalchemy import func
from sqlalchemy.orm.session import Session
from .zonerecord import ZoneRecord
from . import utils as zutils

EMSG_SESSION_TYPE_INVALID = 'Argument session must be an instance of sqlalchemy.orm.session.Session'
EMSG_MULTIVALUE_TYPE_INVALID = "Record values must be a str or list/tuple of str"


def get_records(session, namespace, origin, name=None, type=None):
    if not isinstance(session, Session):
        raise ValueError(EMSG_SESSION_TYPE_INVALID)
    originWithDot = zutils.origin_with_dot(origin)
    q = session.query(ZoneRecord)
    q = q.filter(
        ZoneRecord.namespace == namespace,
        ZoneRecord.origin == originWithDot)
    if name is not None:
        q = q.filter(ZoneRecord.name == name)
    if type:
        q = q.filter(ZoneRecord.type == type)
    records = q.all()
    session.commit()
    return records


def get_namespace_zones(session, origin=None, namespace=None):
    if not isinstance(session, Session):
        raise ValueError(EMSG_SESSION_TYPE_INVALID)
    originWithDot = zutils.origin_with_dot(origin) if origin else None
    q = session.query(ZoneRecord.namespace, ZoneRecord.origin)
    if namespace:
        q = q.filter(ZoneRecord.namespace == namespace)
    if originWithDot:
        q = q.filter(ZoneRecord.origin == originWithDot)
    q = q.distinct(ZoneRecord.namespace, ZoneRecord.origin)
    records = q.all()
    session.commit()
    return records


def set_records(session, origin, namespace, name, type, data, ttl=None):
    if not isinstance(session, Session):
        raise ValueError(EMSG_SESSION_TYPE_INVALID)
    originWithDot = zutils.origin_with_dot(origin)
    if isinstance(data, str):
        data = [data]
    elif not (isinstance(data, (list, tuple)) and all([isinstance(v, str) for v in data])):
        raise validators.utils.ValidationFailure(EMSG_MULTIVALUE_TYPE_INVALID)
    try:
        q = session.query(ZoneRecord)
        q = q.filter(
            ZoneRecord.origin == originWithDot,
            ZoneRecord.namespace == namespace,
            ZoneRecord.name == name)
        if type not in ('CNAME',):
            q = q.filter(ZoneRecord.type == type)
        records = q.all()

        add_items = []
        if records is None or len(records) == 0:
            # 既存レコードが存在しない場合は INSERT動作
            add_items, remove_items = _merge_set_records([], originWithDot, namespace, name, type, data, ttl)
        else:
            # 既存レコードが存在する場合はレコード数に合わせてUPDATE/INSERT/DELETEします。
            add_items, remove_items = _merge_set_records(records, originWithDot, namespace, name, type, data, ttl)
        for r in remove_items:
            session.delete(r)
        session.add_all(add_items)
        session.commit()
        session.flush()
        return [r.to_dict() for r in add_items], [r.to_dict() for r in remove_items]
    except Exception:
        session.rollback()
        raise


def delete_records(session, origin, namespace, name=None, type=None):
    if not isinstance(session, Session):
        raise ValueError(EMSG_SESSION_TYPE_INVALID)
    originWithDot = zutils.origin_with_dot(origin)
    try:
        q = session.query(ZoneRecord)
        q = q.filter(
            ZoneRecord.origin == originWithDot,
            ZoneRecord.namespace == namespace)
        if name is not None:
            q = q.filter(ZoneRecord.name == name)
        if type is not None:
            q = q.filter(ZoneRecord.type == type)
        records = q.all()

        for r in records:
            session.delete(r)
        session.commit()
        session.flush()
        return [r.to_dict() for r in records]
    except Exception:
        session.rollback()


def _merge_set_records(records, originWithDot, namespace, name, type, data, ttl=None):
    # 既存レコードが存在する場合はレコード数に合わせてUPDATE/INSERT/DELETEします。
    add = []
    remove = []
    for r, v in itertools.zip_longest(records, data):
        if r is None:
            if ttl is None:
                ttl = 60
            add.append(ZoneRecord({
                "name": name, "type": type,
                "origin": originWithDot, "namespace": namespace,
                "ttl": ttl, "data": v}))
        elif v is None:
            remove.append(r)
        else:
            r.data = v
            r.type = type
            if ttl is not None:
                r.ttl = ttl
            add.append(r)
    return add, remove


def set_soa_records(session, origin, namespace, nameserver, email,
                    name='@', serial=None, refresh=None, retry=None, expire=None, minimum=None, ttl=600):
    if not isinstance(session, Session):
        raise ValueError(EMSG_SESSION_TYPE_INVALID)
    originWithDot = zutils.origin_with_dot(origin)
    try:
        q = session.query(ZoneRecord)
        q = q.filter(
            ZoneRecord.origin == originWithDot,
            ZoneRecord.namespace == namespace,
            ZoneRecord.name == name,
            ZoneRecord.type == 'SOA')
        records = q.all()

        mname = zutils.origin_with_dot(nameserver)
        rname = zutils.email_to_rname(email)
        updates = {
            'mname': mname, 'rname': rname,
            'serial': serial, 'refresh': refresh, 'retry': retry,
            'expire': expire, 'minimum': minimum}
        if records:
            record = records[0]
            for k, v in updates.items():
                if v is not None:
                    setattr(record, k, v)
        else:
            params = zutils.create_default_soa_params()
            for k, v in updates.items():
                if v is not None:
                    params[k] = v
            soa = zutils.soa_parameters_to_data(**params)
            record = ZoneRecord({**params,
                                 'origin': originWithDot, 'namespace': namespace,
                                 'name': name, 'type': 'SOA', 'data': soa})
        session.add(record)
        session.commit()
        session.flush()
        return record.to_dict()
    except Exception:
        session.rollback()
        raise


def update_serial(session, origin, namespace, serial=None, force=False):
    if not isinstance(session, Session):
        raise ValueError(EMSG_SESSION_TYPE_INVALID)
    originWithDot = zutils.origin_with_dot(origin)
    try:
        q = session.query(func.max(ZoneRecord.modified_at))
        q = q.filter(
            ZoneRecord.origin == originWithDot,
            ZoneRecord.namespace == namespace)
        lastup = q.one()[0]

        q = session.query(ZoneRecord)
        q = q.filter(
            ZoneRecord.origin == originWithDot,
            ZoneRecord.namespace == namespace,
            ZoneRecord.name == '@',
            ZoneRecord.type == 'SOA')
        records = q.all()
        for r in records:
            if serial is not None:
                soa_params = zutils.soa_parameters_from_data(r.data)
                soa_params['serial'] = serial
                soa = zutils.soa_parameters_to_data(**soa_params)
                r.data = soa
                session.add(r)
            elif force or r.modified_at < lastup:
                soa_params = zutils.soa_parameters_from_data(r.data)
                old_serial = int(soa_params['serial'])
                soa_params['serial'] = old_serial + 1
                soa = zutils.soa_parameters_to_data(**soa_params)
                r.data = soa
                session.add(r)
        session.commit()
        session.flush()
        return [r.to_dict() for r in records]
    except Exception:
        session.rollback()
        raise


get_record = get_records
set_record = set_records
delete_record = delete_records
set_soa_record = set_soa_records
