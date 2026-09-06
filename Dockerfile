# syntax=docker/dockerfile:1.7

# --- Stage 1: build the React frontend --------------------------------------
FROM node:20-alpine AS frontend-build
WORKDIR /build

# Install deps first for layer cache
COPY application/frontend/package.json application/frontend/package-lock.json ./
RUN npm ci

# Build. No VITE_*_API_URL is set here so api.ts falls back to same-origin
# `/api`, which is exactly what the runtime backend serves.
COPY application/frontend/ ./
RUN npm run build


# --- Stage 2: Python runtime ------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVE_STATIC=1 \
    PORT=8080

WORKDIR /app

# Backend deps first (better layer caching than copying source first)
COPY application/backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Backend source
COPY application/backend/ ./

# Built frontend from stage 1
COPY --from=frontend-build /build/dist ./static

EXPOSE 8080

CMD ["sh", "-c", "uvicorn main:app --host localhost --port ${PORT}"]
