FROM python:3.9.1-alpine3.12

RUN apk add --no-cache \
    gcc \
    python3-dev \
    musl-dev \
    postgresql-dev \
    && pip install psycopg2-binary
RUN apk add git vim bash && \
    adduser -u 101 -D bind && \
    mkdir -p /usr/local/src/bind9zone

#RUN pip install -r /usr/local/src/bind9zone/requirements.txt -r /usr/local/src/bind9zone/requirements-test.txt
COPY ./setup.py requirements.txt requirements-test.txt /usr/local/src/bind9zone/
COPY --chown=bind ./bind9zone /usr/local/src/bind9zone/bind9zone
COPY --chown=bind ./tests /usr/local/src/bind9zone/tests
RUN pip install -e '/usr/local/src/bind9zone/[test]'

USER bind
