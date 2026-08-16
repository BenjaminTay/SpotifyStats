FROM python:3.9-slim AS backend

WORKDIR /app
COPY requirements-analytics.txt .
RUN pip install --no-cache-dir -r requirements-analytics.txt
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt
COPY requirements-features.txt .
RUN pip install --no-cache-dir -r requirements-features.txt
COPY requirements-search.txt .
RUN pip install --no-cache-dir -r requirements-search.txt
COPY backend/ ./backend/
COPY scripts/ ./scripts/
RUN python scripts/validate_container_image.py /app
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV SPOTIFY_STATS_WARMUP=1

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM node:22-alpine AS frontend

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps
COPY frontend/ ./
RUN npm run build

FROM nginx:alpine AS frontend-server
ARG NGINX_CONFIG=nginx.conf
COPY --from=frontend /app/dist /usr/share/nginx/html
COPY ${NGINX_CONFIG} /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
