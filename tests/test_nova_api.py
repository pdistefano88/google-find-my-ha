import binascii
import types

import pytest

from google_find_my_ha.NovaApi import nova_request, util
from google_find_my_ha.NovaApi.ExecuteAction import nbe_execute_action
from google_find_my_ha.NovaApi.ListDevices import nbe_list_devices
from google_find_my_ha.ProtoDecoders import DeviceUpdate_pb2


def test_utilities(monkeypatch):
    monkeypatch.setattr(util.uuid, "uuid4", lambda: "uuid")
    assert util.generate_random_uuid() == "uuid"
    assert util.flip_bits(b"\x00\x55\xff", True) == b"\xff\xaa\x00"
    assert util.flip_bits(b"abc", False) == b"abc"
    assert util.hours_to_seconds(2.5) == 9000


def test_nova_request_success_posts_binary_payload(monkeypatch):
    captured = {}
    monkeypatch.setattr(nova_request, "get_username", lambda: "user")
    monkeypatch.setattr(nova_request, "get_adm_token", lambda username: "token")

    def fake_post(url, headers, data):
        captured.update(url=url, headers=headers, data=data)
        return types.SimpleNamespace(status_code=200, content=b"\x01\x02")

    monkeypatch.setattr(nova_request.requests, "post", fake_post)
    assert nova_request.nova_request("scope", "00ff") == "0102"
    assert captured["url"].endswith("/nova/scope")
    assert captured["headers"]["Authorization"] == "Bearer token"
    assert captured["data"] == b"\x00\xff"


def test_nova_request_error_raises_text(monkeypatch):
    monkeypatch.setattr(nova_request, "get_username", lambda: "user")
    monkeypatch.setattr(nova_request, "get_adm_token", lambda username: "token")
    monkeypatch.setattr(nova_request.requests, "post", lambda **kwargs: None)
    monkeypatch.setattr(
        nova_request.requests,
        "post",
        lambda url, headers, data: types.SimpleNamespace(status_code=403, text="<html>denied</html>"),
    )
    with pytest.raises(ValueError) as exc_info:
        nova_request.nova_request("scope", "00")
    assert "denied" in str(exc_info.value)


def test_create_action_request_and_serialization():
    request = nbe_execute_action.create_action_request("canonic", "gcm", request_uuid="req", fmd_client_uuid="client")
    assert request.scope.type == DeviceUpdate_pb2.DeviceType.SPOT_DEVICE
    assert request.scope.device.canonicId.id == "canonic"
    assert request.requestMetadata.requestUuid == "req"
    assert request.requestMetadata.gcmRegistrationId.id == "gcm"
    parsed = DeviceUpdate_pb2.ExecuteActionRequest()
    parsed.ParseFromString(binascii.unhexlify(nbe_execute_action.serialize_action_request(request)))
    assert parsed == request


def test_create_device_list_request_sets_spot_type_and_uuid(monkeypatch):
    monkeypatch.setattr(nbe_list_devices, "generate_random_uuid", lambda: "uuid")
    parsed = DeviceUpdate_pb2.DevicesListRequest()
    parsed.ParseFromString(bytes.fromhex(nbe_list_devices.create_device_list_request()))
    assert parsed.deviceListRequestPayload.type == DeviceUpdate_pb2.DeviceType.SPOT_DEVICE
    assert parsed.deviceListRequestPayload.id == "uuid"


def test_request_device_list_delegates_to_nova(monkeypatch):
    calls = []
    monkeypatch.setattr(nbe_list_devices, "create_device_list_request", lambda: "payload")
    monkeypatch.setattr(nbe_list_devices, "nova_request", lambda scope, payload: calls.append((scope, payload)) or "result")
    assert nbe_list_devices.request_device_list() == "result"
    assert calls == [(nbe_list_devices.NOVA_LIST_DEVICS_API_SCOPE, "payload")]
