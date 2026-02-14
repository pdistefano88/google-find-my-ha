# GoogleFindMyTools Home Assistant

This is based on https://github.com/leonboe1/GoogleFindMyTools and https://github.com/endeavour/GoogleFindMyTools-homeassistant.

With respect to the latter, I have done some refactoring, type hinting and removal of redundant code. Most importantly, 
I provide a Dockerfile to run the app as a service. 

----
Describe how to get Auth
----


- MQTT_BROKER: MQTT broker host
- MQTT_PORT: MQTT port, defaults to "1883"
- MQTT_USERNAME: MQTT username
- MQTT_PASSWORD: MQTT password
- POLL_INTERVAL: Poll interval in seconds. Location data will be pulled accordingly.
- LOG_LEVEL: Log level, defaults to INFO

It includes a new script, publish_mqtt.py that will publish the location of all your devices to an MQTT broker. These devices are then discoverable by home assistant and you can display them on a map, make automations etc.

Just run this script on a cronjob every so often to keep things up to date.
