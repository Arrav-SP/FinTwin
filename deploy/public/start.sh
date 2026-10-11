#!/bin/bash
# Starts PostgreSQL inside the container, then the FinTwin server. Used only by the all-in-one image.
# PostgreSQL is kept small: the host this image is meant for has 512 MB for everything.
set -e
OPTIONS="-c listen_addresses=127.0.0.1 -c unix_socket_directories=/tmp -c shared_buffers=24MB -c max_connections=40 -c work_mem=2MB -c maintenance_work_mem=16MB"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  # Normally done while the image is built. This covers a data directory that was replaced.
  initdb -U fintwin --auth=trust -E UTF8 > /dev/null
  pg_ctl -D "$PGDATA" -o "$OPTIONS" -w -l /tmp/postgres.log start
  createdb -h 127.0.0.1 -U fintwin fintwin
  gunzip -c bundled/database.sql.gz | psql -h 127.0.0.1 -U fintwin -d fintwin -q -v ON_ERROR_STOP=1 > /dev/null
else
  pg_ctl -D "$PGDATA" -o "$OPTIONS" -w -l /tmp/postgres.log start
fi

exec python scripts/serve.py
