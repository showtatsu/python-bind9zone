FROM python:3.9.1-alpine3.12

RUN apk add --no-cache \
    gcc \
    python3-dev \
    musl-dev \
    postgresql-dev \
    && pip install psycopg2-binary
RUN apk add git vim bash && adduser -u 101 -D bind
USER bind
WORKDIR /home/bind
COPY ./requirements.txt ./requirements-test.txt ./
RUN pip install -r requirements.txt -r ./requirements-test.txt
COPY --chown=bind ./bind9zone ./bind9zone
COPY --chown=bind ./tests ./tests
COPY --chown=bind setup.py ./
RUN pip install -e '.[test]'

USER root
RUN apk add --no-cache nodejs
USER bind