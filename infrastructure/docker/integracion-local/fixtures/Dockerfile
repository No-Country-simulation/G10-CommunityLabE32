FROM python:3.12-alpine
RUN apk add --no-cache postgresql-client \
    && adduser -D -u 10001 fixture
WORKDIR /app
COPY fixture.py healthcheck.py ./
USER fixture
CMD ["python", "-u", "/app/fixture.py"]
