FROM python:3.12-alpine
RUN apk add --no-cache postgresql-client && adduser -D -u 10001 worker
WORKDIR /app
COPY probe.py healthcheck.py ./
USER worker
CMD ["python", "-u", "/app/probe.py"]
