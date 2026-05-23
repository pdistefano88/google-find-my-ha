import types

import pytest

from google_find_my_ha.nova_api.execute_action.locate_tracker import location_request
from google_find_my_ha.proto_decoders import device_update_pb2


def test_create_location_request_sets_locate_tracker_fields():
    parsed = device_update_pb2.ExecuteActionRequest()
    parsed.ParseFromString(bytes.fromhex(location_request.create_location_request("canonic", "fcm", "req")))
    assert parsed.action.locateTracker.lastHighTrafficEnablingTime.seconds == 1732120060
    assert parsed.action.locateTracker.contributorType == device_update_pb2.SpotContributorType.FMDN_ALL_LOCATIONS
    assert parsed.requestMetadata.requestUuid == "req"


def test_get_location_data_success_uses_matching_fcm_response(monkeypatch):
    callbacks = []

    class Receiver:
        def register_for_location_updates(self, callback, timeout_seconds):
            callbacks.append(callback)
            return "fcm-token"

        def unregister_location_update_callback(self, callback):
            callbacks.remove(callback)

    first = types.SimpleNamespace(fcmMetadata=types.SimpleNamespace(requestUuid="other"))
    second = types.SimpleNamespace(fcmMetadata=types.SimpleNamespace(requestUuid="req"))
    parsed = iter([first, second, second])
    monkeypatch.setattr(location_request, "generate_random_uuid", lambda: "req")
    monkeypatch.setattr(location_request, "FcmReceiver", Receiver)
    monkeypatch.setattr(location_request, "parse_device_update_protobuf", lambda response: next(parsed))
    monkeypatch.setattr(location_request, "create_location_request", lambda *args: "hex")

    def fake_nova(scope, payload):
        callbacks[0]("ignored")
        callbacks[0]("matched")

    monkeypatch.setattr(location_request, "nova_request", fake_nova)
    monkeypatch.setattr(location_request, "decrypt_location_response_locations", lambda result: {"ok": True})

    assert location_request.get_location_data_for_device("canonic", "Tracker") == {"ok": True}
    assert callbacks == []


def test_get_location_data_timeout_unregisters_callback(monkeypatch):
    callbacks = []
    times = iter([0, 2])

    class Receiver:
        def register_for_location_updates(self, callback, timeout_seconds):
            callbacks.append(callback)
            return "fcm-token"

        def unregister_location_update_callback(self, callback):
            callbacks.remove(callback)

    monkeypatch.setattr(location_request, "TIMEOUT", 1)
    monkeypatch.setattr(location_request, "generate_random_uuid", lambda: "req")
    monkeypatch.setattr(location_request, "FcmReceiver", Receiver)
    monkeypatch.setattr(location_request, "create_location_request", lambda *args: "hex")
    monkeypatch.setattr(location_request, "nova_request", lambda scope, payload: None)
    monkeypatch.setattr(location_request.time, "monotonic", lambda: next(times))
    with pytest.raises(TimeoutError):
        location_request.get_location_data_for_device("canonic", "Tracker")
    assert callbacks == []
