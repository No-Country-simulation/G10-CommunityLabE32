FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt

COPY worker/requirements.txt ./worker/requirements.txt
COPY pipelines/communitylab/requirements-lock.txt ./pipelines/communitylab/requirements-lock.txt

RUN pip install --no-cache-dir -r backend/requirements.txt \
    && useradd --uid 10001 --create-home app

COPY backend ./backend
COPY pipelines ./pipelines
COPY worker ./worker

USER app

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
