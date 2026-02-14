import json
import logging
import os
import time
from time import sleep

import paho.mqtt.client as mqtt

from google_find_my_ha.NovaApi.ExecuteAction.LocateTracker.decrypt_locations import SemanticData, LocationData
from google_find_my_ha.NovaApi.ExecuteAction.LocateTracker.location_request import get_location_data_for_device
from google_find_my_ha.NovaApi.ListDevices.nbe_list_devices import request_device_list
from google_find_my_ha.ProtoDecoders.decoder import parse_device_list_protobuf, get_canonic_ids

logging.basicConfig(level=os.environ.get('LOG_LEVEL', logging.DEBUG))
logger = logging.getLogger(__name__)

# MQTT Configuration
MQTT_BROKER = os.environ.get("MQTT_BROKER")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1887"))
MQTT_USERNAME = os.environ.get("MQTT_USERNAME")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_CLIENT_ID = "google_find_my_publisher"
HOME_LATITUDE = float(os.environ.get("HOME_LATITUDE", "0"))
HOME_LONGITUDE = float(os.environ.get("HOME_LONGITUDE", "0"))
HOME_ALTITUDE = float(os.environ.get("HOME_ALTITUDE", "0"))

POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "60"))

# Home Assistant MQTT Discovery
DISCOVERY_PREFIX = "homeassistant"
DEVICE_PREFIX = "google_find_my"


def on_connect(client, userdata, flags, result_code, properties):
    """Callback when connected to MQTT broker"""
    logger.info(f"Connected to MQTT broker with result code {result_code}")


def publish_device_config(client: mqtt.Client, device_name: str, canonic_id: str) -> None:
    """Publish Home Assistant MQTT discovery configuration for a device"""
    base_topic = f"{DISCOVERY_PREFIX}/device_tracker/{DEVICE_PREFIX}_{canonic_id}"

    # Device configuration for Home Assistant
    config = {
        "unique_id": f"{DEVICE_PREFIX}_{canonic_id}",
        "state_topic": f"{base_topic}/state",
        "json_attributes_topic": f"{base_topic}/attributes",
        "source_type": "gps",
        "device": {
            "identifiers": [f"{DEVICE_PREFIX}_{canonic_id}"],
            "name": device_name,
            "model": "Google Find My Device",
            "manufacturer": "Google"
        }
    }
    logger.info(f"{base_topic}/config")
    # Publish discovery config
    r = client.publish(f"{base_topic}/config", json.dumps(config), retain=True)
    return r


def publish_device_state(client: mqtt.Client, canonic_id: str,
                         location_data: SemanticData | LocationData) -> mqtt.MQTTMessageInfo:
    """Publish device state and attributes to MQTT"""
    base_topic = f"{DISCOVERY_PREFIX}/device_tracker/{DEVICE_PREFIX}_{canonic_id}"
    home = str(location_data.get("semantic_location")).lower() == "home"

    # Extract location data
    lat = location_data.get('latitude', HOME_LATITUDE if home else None)
    lon = location_data.get('longitude', HOME_LONGITUDE if home else None)
    accuracy = location_data.get('accuracy')
    altitude = location_data.get('altitude', HOME_ALTITUDE if home else None)
    timestamp = location_data.get('timestamp', time.time())

    # Publish attributes
    attributes = {
        "latitude": lat,
        "longitude": lon,
        "altitude": altitude,
        "gps_accuracy": accuracy,
        "source_type": "gps",
        "last_updated": timestamp
    }
    r = client.publish(f"{base_topic}/attributes", json.dumps(attributes))
    return r


def main():
    # Initialize MQTT client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, MQTT_CLIENT_ID)
    client.on_connect = on_connect

    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
        client.loop_start()

        logger.info("Loading devices...")
        result_hex = request_device_list()
        device_list = parse_device_list_protobuf(result_hex)
        canonic_ids = get_canonic_ids(device_list)

        logger.info(f"Found {len(canonic_ids)} devices")

        # Publish discovery config and state for each device
        for device_name, canonic_id in canonic_ids:
            logger.info(f"Processing device: {device_name}")

            # Publish discovery configuration
            msg_info = publish_device_config(client, device_name, canonic_id)
            msg_info.wait_for_publish()
        logger.info("All devices have been published to MQTT")
        logger.info("Devices will now be discoverable in Home Assistant")
        logger.info("You may need to restart Home Assistant or trigger device discovery")

        while True:
            for device_name, canonic_id in canonic_ids:
                try:
                    location_data = get_location_data_for_device(canonic_id, device_name)
                    msg_info = publish_device_state(client, canonic_id, location_data)
                    msg_info.wait_for_publish()

                    logger.info(f"Published data for {device_name}")
                except Exception as e:
                    logger.exception(f"Failed to retrieve data for device {device_name}. Error: {e}")
            sleep(POLL_INTERVAL)


    except Exception as e:
        logger.exception(f"Error: {e}")

    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == '__main__':
    main()
