FROM python:3.12
LABEL authors="pietro"

ENV MQTT_BROKER ""
ENV MQTT_PORT "1883"
ENV MQTT_USERNAME ""
ENV MQTT_PASSWORD ""
ENV POLL_INTERVAL "30"
ENV LOG_LEVEL "INFO"
ENV SECRETS_DIR "/var"

COPY google_find_my_ha ./google_find_my_ha
COPY publish_mqtt.py .
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

ENTRYPOINT ["python", "publish_mqtt.py"]
