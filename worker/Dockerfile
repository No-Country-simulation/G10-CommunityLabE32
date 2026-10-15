FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
COPY worker/requirements.txt ./worker/requirements.txt
COPY pipelines/communitylab/requirements-lock.txt ./pipelines/communitylab/requirements-lock.txt
COPY pipelines ./pipelines
COPY worker ./worker

RUN pip install --no-cache-dir -r ./backend/requirements.txt \
    && useradd --uid 10001 --create-home worker

COPY backend/app/pipelines ./backend/app/pipelines
COPY backend/app/core ./backend/app/core
COPY backend/app/models ./backend/app/models

USER worker
CMD ["python", "-m", "worker.run"]
