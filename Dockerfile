FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src /app/src
COPY migrations /app/migrations
COPY bin /app/bin

ENV PYTHONPATH=/app/src
ENTRYPOINT ["python", "-m", "mail_archiver.cli"]
