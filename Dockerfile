# Stage 1: build the web interface to static files.
FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: the API, which also serves the built interface.
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY backend/requirements.txt backend/constraints.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt -c backend/constraints.txt
COPY backend backend
COPY database database
COPY scripts scripts
COPY bundled bundled
COPY --from=web /web/dist web/dist
EXPOSE 8000
CMD ["python", "scripts/serve.py"]
