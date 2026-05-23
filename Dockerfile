FROM python:3.12
LABEL authors="pietro"

COPY --from=ghcr.io/astral-sh/uv:0.11.12 /uv /uvx /bin/

WORKDIR /app

ENV MQTT_BROKER=""
ENV MQTT_PORT="1883"
ENV POLL_INTERVAL="30"
ENV LOG_LEVEL="INFO"
ENV SECRETS_DIR="/var"

COPY google_find_my_ha ./google_find_my_ha
COPY publish_mqtt.py .
COPY chrome_driver.py .
COPY pyproject.toml .
COPY README.md .

RUN uv pip install --system --no-cache .

ENTRYPOINT ["python", "publish_mqtt.py"]
