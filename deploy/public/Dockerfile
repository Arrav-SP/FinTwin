# All-in-one image for the public website: PostgreSQL, the API and the built interface in one
# container, running as an ordinary user. Build it from the repository root:
#   docker build -f deploy/public/Dockerfile -t fintwin-public .
# The host supplies the port in $PORT (Render does). See docs/DEPLOY.md.

FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM postgres:16-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 1000 fintwin
USER fintwin
ENV HOME=/home/fintwin \
    PGDATA=/home/fintwin/pgdata \
    PATH=/home/fintwin/venv/bin:/usr/lib/postgresql/16/bin:$PATH \
    PYTHONPATH=/home/fintwin/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=postgresql+psycopg://fintwin@127.0.0.1:5432/fintwin \
    FINTWIN_PUBLIC=true
WORKDIR /home/fintwin/app

RUN python3 -m venv /home/fintwin/venv
COPY --chown=fintwin backend/requirements.txt backend/constraints.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt -c backend/constraints.txt

# Load the recorded reference runs while building, so a restart takes seconds instead of a minute.
COPY --chown=fintwin bundled bundled
RUN initdb -U fintwin --auth=trust -E UTF8 > /dev/null \
 && pg_ctl -D "$PGDATA" -o "-c listen_addresses=127.0.0.1 -c unix_socket_directories=/tmp" -w start \
 && createdb -h 127.0.0.1 -U fintwin fintwin \
 && gunzip -c bundled/database.sql.gz | psql -h 127.0.0.1 -U fintwin -d fintwin -q -v ON_ERROR_STOP=1 > /dev/null \
 && pg_ctl -D "$PGDATA" -m fast -w stop \
 && rm bundled/database.sql.gz

COPY --chown=fintwin backend backend
COPY --chown=fintwin database database
COPY --chown=fintwin scripts scripts
COPY --chown=fintwin deploy/public/start.sh start.sh
COPY --from=web --chown=fintwin /web/dist web/dist

EXPOSE 10000
ENTRYPOINT []
CMD ["bash", "start.sh"]
