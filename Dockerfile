FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --create-home --uid 10001 airspace
COPY backend/pyproject.toml backend/alembic.ini ./
COPY backend/airspace ./airspace
COPY backend/migrations ./migrations
RUN pip install --no-cache-dir .
COPY --from=frontend /build/dist ./airspace/static
RUN mkdir -p /app/data && chown -R airspace:airspace /app
USER airspace
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD ["python","-c","import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live',timeout=3)"]
CMD ["uvicorn","airspace.main:app","--host","0.0.0.0","--port","8000"]
