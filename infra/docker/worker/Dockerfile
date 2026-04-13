FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY packages/source-adapters /app/packages/source-adapters
COPY apps/worker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY apps/worker /app/apps/worker

WORKDIR /app/apps/worker

CMD ["python", "-m", "app.main"]

