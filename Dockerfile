FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends lua5.4 curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY knowledge/ knowledge/
COPY scripts/ scripts/

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
