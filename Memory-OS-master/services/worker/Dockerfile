# Build from repository root:
#   docker build -f services/worker/Dockerfile .
FROM python:3.12-slim
WORKDIR /app
COPY services/api/requirements.txt ./api/requirements.txt
COPY services/api/app ./api/app
COPY services/api/alembic ./api/alembic
COPY services/api/alembic.ini ./api/alembic.ini
COPY services/worker/worker ./worker
RUN pip install --no-cache-dir -r ./api/requirements.txt
ENV PYTHONPATH=/app/api:/app
CMD ["celery", "-A", "worker.celery_app", "worker", "--loglevel=info", "-Q", "memoryos"]
