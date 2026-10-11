#!/bin/bash
# Starts PostgreSQL inside the container, then the FinTwin server. Used only by the all-in-one image.
set -e
OPTIONS="-c listen_addresses=127.0.0.1 -c unix_socket_directories=/tmp"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  # Normally done while the image is built; this covers a data directory that was replaced.
  initdb -U fintwin --auth=trust -E UTF8 > /dev/null
  pg_ctl -D "$PGDATA" -o "$OPTIONS" -w -l /tmp/postgres.log start
  createdb -h 127.0.0.1 -U fintwin fintwin
  cat bundled/database.sql.gz.part* | gunzip | psql -h 127.0.0.1 -U fintwin -d fintwin -q -v ON_ERROR_STOP=1 > /dev/null
else
  pg_ctl -D "$PGDATA" -o "$OPTIONS" -w -l /tmp/postgres.log start
fi

exec python scripts/serve.py
