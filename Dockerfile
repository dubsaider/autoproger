# Сборка фронтенда
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/ .
RUN npm install && npm run build

# Приложение
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /build/dist ./frontend/dist

EXPOSE 8000
CMD ["uvicorn", "src.admin.app:app", "--host", "0.0.0.0", "--port", "8000"]
