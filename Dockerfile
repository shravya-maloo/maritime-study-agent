FROM python:3.12-slim

# Slim images ship without CA certificates, and then every HTTPS call
# (Telegram, the AI API) fails. Maritime's starter installs them, so do we.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# start.py reads $PORT (set by Maritime) and starts the web server.
CMD ["python", "start.py"]
