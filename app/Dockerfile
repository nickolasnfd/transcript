# Backend + frontend buildado, servidos pelo mesmo Uvicorn
FROM node:22-slim AS frontend
WORKDIR /build
COPY app/frontend/package*.json ./
RUN npm ci
COPY app/frontend .
RUN npm run build

FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
# Lib whisper deste repositório (instalada como dependência, sem modificações)
COPY pyproject.toml MANIFEST.in README.md ./
COPY whisper ./whisper
RUN pip install --no-cache-dir .

COPY app/backend/requirements.txt /tmp/reqs.txt
RUN pip install --no-cache-dir -r /tmp/reqs.txt

COPY app/backend ./app/backend
COPY --from=frontend /build/dist ./app/frontend/dist
RUN touch app/__init__.py

ENV DATA_DIR=/data PORT=8000
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
