# All-in-one image for a public demonstration: PostgreSQL, the API and the built interface in one
# container, running as an ordinary user on port 7860 (what Hugging Face Spaces expects).
# Generated into build/space by scripts/build_space.py; build it from there.

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
    FINTWIN_PUBLIC=true \
    FINTWIN_PORT=7860
WORKDIR /home/fintwin/app

RUN python3 -m venv /home/fintwin/venv
COPY --chown=fintwin backend/requirements.txt backend/constraints.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt -c backend/constraints.txt

# Load the recorded runs while building, so a restart takes seconds instead of a minute.
COPY --chown=fintwin bundled bundled
RUN initdb -U fintwin --auth=trust -E UTF8 > /dev/null \
 && pg_ctl -D "$PGDATA" -o "-c listen_addresses=127.0.0.1 -c unix_socket_directories=/tmp" -w start \
 && createdb -h 127.0.0.1 -U fintwin fintwin \
 && cat bundled/database.sql.gz.part* | gunzip | psql -h 127.0.0.1 -U fintwin -d fintwin -q -v ON_ERROR_STOP=1 > /dev/null \
 && pg_ctl -D "$PGDATA" -m fast -w stop \
 && rm bundled/database.sql.gz.part*

COPY --chown=fintwin backend backend
COPY --chown=fintwin database database
COPY --chown=fintwin scripts scripts
COPY --chown=fintwin start.sh start.sh
COPY --from=web --chown=fintwin /web/dist web/dist

EXPOSE 7860
ENTRYPOINT []
CMD ["bash", "start.sh"]
