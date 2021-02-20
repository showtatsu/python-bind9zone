import re
import validators
import itertools
from datetime import datetime, timedelta, timezone
from sqlalchemy import Table, Column, MetaData, create_engine, and_, or_, distinct
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Session, sessionmaker, scoped_session, validates
from sqlalchemy.types import DateTime, Integer, String, Float, Integer, Boolean, Date, BigInteger
from sqlalchemy.ext.declarative import declarative_base
JST = timezone(timedelta(hours=+9), 'JST')
Base = declarative_base()


class ZoneRecord(Base):

    __tablename__ = "bind9zone_zone_records"
    __table_args__ = {'sqlite_autoincrement': True}
    
    id = Column('id', BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True, autoincrement=True)
    name = Column('name', String(), nullable=False)
    type = Column('type', String())
    data = Column('data', String(), nullable=False)
    _ttl = Column('ttl', Integer())
    origin = Column('origin', String(), nullable=False)
    namespace = Column('namespace', String())
    fqdn = Column('fqdn', String(), index=True)
    created_by = Column('created_by', String())
    modified_by = Column('modified_by', String())
    created_at = Column('created_at', DateTime(timezone=False), default=datetime.now())
    modified_at = Column('modified_at', DateTime(timezone=False), default=datetime.now(), onupdate=datetime.now())

    def __init__(self, record):
        keys = record.keys()
        for c in self.__table__.columns:
            if c.name in keys:
                setattr(self, c.name, record[c.name])
        self.fqdn = self.get_fqdn()


    @hybrid_property
    def ttl(self):
        return self._ttl
    
    @ttl.setter
    def ttl(self, value):
        if value is None:
            self._ttl = None
        elif str(value).isdigit():
            self._ttl = int(value)
        else:
            m = re.match(r'^(?P<digit>[0-9]+)(?P<unit>[MHDW])$', value.upper())
            if m is not None:
                t = int(m.group('digit'))
                u = ({'M':60, 'H': 3600, 'D': 86400, 'W': 604800})[m.group('unit')]
                self._ttl = t * u
            else:
                raise ValueError('TTL must be a digit.')

    @validates('name')
    def name_validate(self, key, name):
        if name is None:
            raise ValueError('name must not be NULL')
        return name

    @validates('data')
    def data_validate(self, key, data):
        if data is None:
            raise ValueError('data must not be NULL')
        return data

    @validates('origin')
    def origin_validate(self, key, origin):
        if origin is None:
            raise ValueError('origin must not be NULL')
        elif origin.endswith('.') and validators.domain(origin[:-1]):
            return origin
        else:
            raise ValueError('origin must be a domain string with trailing dot="."')
    
    @validates('namespace')
    def namespace_validate(self, key, namespace):
        if namespace is None or validators.slug(namespace):
            return namespace
        raise ValueError('namespace must be a slug string')

    def compare(self, other):
        keys = ['name', 'type', 'data', 'ttl', 'origin', 'namespace']
        if not isinstance(other, ZoneRecord):
            raise ValueError('ZoneRecord is not comparable with {}'.format(type(other)))
        return all([getattr(self, k) == getattr(other, k) for k in keys])

    def to_record(self, origin=None, withId=True):
        if origin is None:
            origin = self.origin
        origin = re.sub(r'\.$', '',  re.sub(r'^@\.', '', origin))
        if origin == '' or self.fqdn.endswith(origin):
            name = self.fqdn[0:len(self.fqdn) - len(origin)].rstrip('.')
        else:
            name = self.fqdn + '.'
        if len(name) == 0:
            name = '@'
        comment = ''
        if withId:
            comment += ' ; meta=(id={})'.format(self.id)
        ttl = self.ttl if self.ttl is not None else ''
        if self.type == 'SOA':
            return '{} {} IN {} {}{}'.format(name, ttl, self.type, self.get_soa_text(), comment)
        else:
            return '{} {} IN {} {}{}'.format(name, ttl, self.type, self.data, comment)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns if getattr(self, c.name) is not None}

    def get_fqdn(self):
        if not self.name.startswith('$'):
            if self.name.endswith('.'):
                fqdn = self.name
            else:
                fqdn = self.name + '.' + self.origin
            return re.sub(r'\.$', '',  re.sub(r'^@\.', '', fqdn))

    def get_soa_params(self):
        pattern = r'(?P<data>(?:(?P<dns>[0-9A-Za-z.-]+)\s+)(?:(?P<email>[0-9A-Za-z.-]+)\s+)\(\s*(?P<serial>[0-9]+)\s+(?P<refresh>[0-9]+)\s+(?P<retry>[0-9]+)\s+(?P<expire>[0-9]+)\s+(?P<minimum>[0-9]+)\s*\))'
        if self.type == 'SOA':
            soa = re.search(pattern, self.data)
            if soa:
                return soa.groupdict()

    def get_soa_text(self):
        soa = self.get_soa_params()
        if soa:
            return '{dns} {email} ( {serial} {refresh} {retry} {expire} {minimum} )'.format(**soa)


    @classmethod
    def delete_origin_from_database(cls, scopedSession, origin, namespace=None):
        origin = origin.rstrip('.')
        if not validators.domain(re.sub(r'\.$', '', origin)):
            raise Exception('Invalid Origin Name, {}'.format(origin))
        if namespace and not validators.slug(namespace):
            raise Exception('Invalid Namespace, {}'.format(namespace))
        originWithDot = origin + '.'
        session = scopedSession()
        try:
            records = session.query(cls)
            records = records.filter(cls.origin == originWithDot)
            if namespace is not None:
                records = records.filter(cls.namespace == namespace)
            count = records.delete()
            session.commit()
            return count
        finally:
            session.close()


    @classmethod
    def from_database(cls, scopedSession, origin, namespace=None):
        origin = origin.rstrip('.')
        if not validators.domain(re.sub(r'\.$', '', origin)):
            raise Exception('Invalid Origin Name, {}'.format(origin))
        if namespace and not validators.slug(namespace):
            raise Exception('Invalid Namespace, {}'.format(namespace))
        originWithDot = origin + '.'
        session = scopedSession()
        try:
            orderPriority = ['SOA']
            records = session.query(cls)
            records = records.filter(cls.origin == originWithDot)
            if namespace is not None:
                records = records.filter(cls.namespace == namespace)
            records = records.all()
            return records
        finally:
            session.close()


    @classmethod
    def get_record(cls, Session, origin, namespace, name, rtype=None):
        origin = origin.rstrip('.')
        if not validators.domain(re.sub(r'\.$', '', origin)):
            raise Exception('Invalid Origin Name, {}'.format(origin))
        if namespace and not validators.slug(namespace):
            raise Exception('Invalid Namespace, {}'.format(namespace))
        originWithDot = origin + '.'
        session = Session()
        try:
            records = session.query(ZoneRecord)
            records = records.filter(ZoneRecord.origin == originWithDot)
            records = records.filter(ZoneRecord.namespace == namespace)
            records = records.filter(ZoneRecord.name == name)
            if rtype is not None:
                records = records.filter(ZoneRecord.type == rtype)
            records = records.all()
            return [r.to_dict() for r in records]
        finally:
            session.close()


    @classmethod
    def set_record(cls, Session, origin, namespace, name, rtype, values, ttl=None):
        origin = origin.rstrip('.')
        if not validators.domain(re.sub(r'\.$', '', origin)):
            raise Exception('Invalid Origin Name, {}'.format(origin))
        if namespace and not validators.slug(namespace):
            raise Exception('Invalid Namespace, {}'.format(namespace))
        originWithDot = origin + '.'
        session = Session()
        try:
            records = session.query(ZoneRecord)
            records = records.filter(ZoneRecord.origin == originWithDot)
            records = records.filter(ZoneRecord.namespace == namespace)
            records = records.filter(ZoneRecord.name == name)
            if rtype != 'CNAME':
                records = records.filter(ZoneRecord.type == rtype)
            records = records.all()

            deleteList = []
            addList = []
            if records is None or len(records) == 0:
                addList.extend([ZoneRecord({
                    "name": name, "type": rtype,
                    "origin": originWithDot, "namespace": namespace,
                    "ttl": ttl, "data": v}) for v in values])
            else:
                for r, v in itertools.zip_longest(records, values):
                    if r is None:
                        addList.append(ZoneRecord({
                            "name": name, "type": rtype,
                            "origin": originWithDot, "namespace": namespace,
                            "ttl": ttl, "data": v}))
                    elif v is None:
                        deleteList.append(r)
                    else:
                        r.data = v
                        if rtype == 'CNAME':
                            r.type = 'CNAME'
                        if ttl is not None:
                            r.ttl = ttl
                        addList.append(r)
            for r in deleteList:
                session.delete(r)
            session.add_all(addList)
            session.commit()
            session.flush()
            return [r.to_dict() for r in addList], [r.to_dict() for r in deleteList]
        finally:
            session.close()


    @classmethod
    def delete_record(cls, Session, origin, namespace, name, rtype=None):
        origin = origin.rstrip('.')
        if not validators.domain(re.sub(r'\.$', '', origin)):
            raise Exception('Invalid Origin Name, {}'.format(origin))
        if namespace and not validators.slug(namespace):
            raise Exception('Invalid Namespace, {}'.format(namespace))
        originWithDot = origin + '.'
        session = Session()
        try:
            records = session.query(ZoneRecord)
            records = records.filter(ZoneRecord.origin == originWithDot)
            records = records.filter(ZoneRecord.namespace == namespace)
            records = records.filter(ZoneRecord.name == name)
            if rtype is not None:
                records = records.filter(ZoneRecord.type == rtype)
            records = records.all()

            deleteList = []
            addList = []
            if records is None or len(records) == 0:
                return
            for r in records:
                session.delete(r)
            session.add_all(addList)
            session.commit()
            session.flush()
            return [r.to_dict() for r in records]
        finally:
            session.close()
