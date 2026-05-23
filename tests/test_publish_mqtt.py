import json
import sys
import types

from conftest import DummyMqttClient


def import_publish_mqtt(monkeypatch, reimport):
    mqtt_module = types.SimpleNamespace(
        CallbackAPIVersion=types.SimpleNamespace(VERSION2=object()),
        Client=lambda *args, **kwargs: DummyMqttClient(),
        MQTTMessageInfo=object,
    )
    monkeypatch.setitem(sys.modules, "paho", types.SimpleNamespace(mqtt=types.SimpleNamespace(client=mqtt_module)))
    monkeypatch.setitem(sys.modules, "paho.mqtt", types.SimpleNamespace(client=mqtt_module))
    monkeypatch.setitem(sys.modules, "paho.mqtt.client", mqtt_module)

    monkeypatch.setitem(sys.modules, "google_find_my_ha.auth.fcm_receiver", types.SimpleNamespace(FcmReceiver=lambda: None))
    monkeypatch.setitem(
        sys.modules,
        "google_find_my_ha.nova_api.execute_action.locate_tracker.decrypt_locations",
        types.SimpleNamespace(LocationData=dict, SemanticData=dict),
    )
    monkeypatch.setitem(
        sys.modules,
        "google_find_my_ha.nova_api.execute_action.locate_tracker.location_request",
        types.SimpleNamespace(get_location_data_for_device=lambda *args: None),
    )
    monkeypatch.setitem(
        sys.modules,
        "google_find_my_ha.nova_api.list_devices.nbe_list_devices",
        types.SimpleNamespace(request_device_list=lambda: ""),
    )
    monkeypatch.setitem(
        sys.modules,
        "google_find_my_ha.proto_decoders.decoder",
        types.SimpleNamespace(parse_device_list_protobuf=lambda payload: [], get_canonic_ids=lambda devices: []),
    )
    return reimport("publish_mqtt")


def test_publish_device_config_writes_home_assistant_discovery(monkeypatch, reimport):
    publish_mqtt = import_publish_mqtt(monkeypatch, reimport)
    client = DummyMqttClient()

    result = publish_mqtt.publish_device_config(client, "Tracker", "abc")
    topic, payload, retain, _ = client.published[0]
    config = json.loads(payload)

    assert topic == "homeassistant/device_tracker/google_find_my_abc/config"
    assert retain is True
    assert result is client.published[0][3]
    assert config["unique_id"] == "google_find_my_abc"
    assert config["device"]["name"] == "Tracker"


def test_publish_device_state_uses_gps_fields(monkeypatch, reimport):
    publish_mqtt = import_publish_mqtt(monkeypatch, reimport)
    client = DummyMqttClient()

    publish_mqtt.publish_device_state(
        client,
        "abc",
        {"latitude": 1.2, "longitude": 3.4, "altitude": 5.6, "accuracy": 7, "timestamp": "now"},
    )
    state_topic, state_payload, state_retain, _ = client.published[0]
    topic, payload, retain, _ = client.published[1]

    assert state_topic == "homeassistant/device_tracker/google_find_my_abc/state"
    assert state_payload == "not_home"
    assert state_retain is False
    assert topic == "homeassistant/device_tracker/google_find_my_abc/attributes"
    assert retain is False
    assert json.loads(payload) == {
        "latitude": 1.2,
        "longitude": 3.4,
        "altitude": 5.6,
        "gps_accuracy": 7,
        "source_type": "gps",
        "last_updated": "now",
    }


def test_publish_device_state_uses_home_coordinates_for_semantic_home(monkeypatch, reimport):
    monkeypatch.setenv("HOME_LATITUDE", "45.1")
    monkeypatch.setenv("HOME_LONGITUDE", "9.2")
    monkeypatch.setenv("HOME_ALTITUDE", "100")
    publish_mqtt = import_publish_mqtt(monkeypatch, reimport)
    client = DummyMqttClient()

    publish_mqtt.publish_device_state(client, "abc", {"semantic_location": "Home", "timestamp": "now"})
    assert client.published[0][1] == "not_home"
    payload = json.loads(client.published[1][1])

    assert payload["latitude"] == 45.1
    assert payload["longitude"] == 9.2
    assert payload["altitude"] == 100.0


def test_publish_device_state_uses_semantic_state_without_coordinates(monkeypatch, reimport):
    publish_mqtt = import_publish_mqtt(monkeypatch, reimport)
    client = DummyMqttClient()

    publish_mqtt.publish_device_state(client, "abc", {"semantic_location": "Work", "timestamp": "now"})

    assert client.published[0][0] == "homeassistant/device_tracker/google_find_my_abc/state"
    assert client.published[0][1] == "Work"
    attributes = json.loads(client.published[1][1])
    assert attributes["latitude"] is None
    assert attributes["longitude"] is None


def test_record_poll_failure_threshold_reconnects_and_resets(monkeypatch, reimport):
    monkeypatch.setenv("FCM_RECONNECT_FAILURE_THRESHOLD", "2")
    publish_mqtt = import_publish_mqtt(monkeypatch, reimport)
    reasons = []
    monkeypatch.setattr(publish_mqtt, "reconnect_fcm", reasons.append)
    counts = {"a": 0, "b": 3}

    publish_mqtt.record_poll_failure(counts, "a", "Tracker", "timeout")
    assert reasons == []
    publish_mqtt.record_poll_failure(counts, "a", "Tracker", "timeout")

    assert "Tracker had 2 consecutive failed polls" in reasons[0]
    assert counts == {"a": 0, "b": 0}


def test_record_poll_failure_disabled_threshold_does_not_reconnect(monkeypatch, reimport):
    monkeypatch.setenv("FCM_RECONNECT_FAILURE_THRESHOLD", "0")
    publish_mqtt = import_publish_mqtt(monkeypatch, reimport)
    monkeypatch.setattr(publish_mqtt, "reconnect_fcm", lambda reason: (_ for _ in ()).throw(AssertionError(reason)))
    counts = {}

    publish_mqtt.record_poll_failure(counts, "a", "Tracker", "timeout")
    assert counts == {"a": 1}
