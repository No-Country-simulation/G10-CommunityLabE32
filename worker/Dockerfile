FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pipelines/communitylab/requirements-lock.txt /tmp/grafo.txt
COPY worker/requirements.txt /tmp/worker.txt
RUN pip install --no-cache-dir -r /tmp/grafo.txt -r /tmp/worker.txt \
    && useradd --uid 10001 --create-home worker
COPY pipelines ./pipelines
COPY backend/app/pipelines ./backend/app/pipelines
COPY worker ./worker
USER worker
CMD ["python", "-m", "worker.run"]
