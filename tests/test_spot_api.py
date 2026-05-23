import types

import pytest

from google_find_my_ha.proto_decoders import common_pb2, device_update_pb2
from google_find_my_ha.spot_api import spot_request
from google_find_my_ha.spot_api.get_eid_info_for_e2ee_devices import (
    get_eid_info_request,
    get_owner_key,
)
from google_find_my_ha.spot_api.grpc_parser import GrpcParser


def test_grpc_construct_extract_roundtrip_and_invalid_inputs():
    payload = b"payload"
    grpc = GrpcParser.construct_grpc(payload)
    assert grpc == b"\x00\x00\x00\x00\x07payload"
    assert GrpcParser.extract_grpc_payload(grpc) == payload
    with pytest.raises(ValueError, match="Invalid GRPC payload"):
        GrpcParser.extract_grpc_payload(b"1234")
    with pytest.raises(ValueError, match="Invalid GRPC payload length"):
        GrpcParser.extract_grpc_payload(b"\x00\x00\x00\x00\x05abc")


def test_spot_request_success_constructs_headers_and_extracts_payload(monkeypatch):
    captured = {}

    class Client:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, content):
            captured.update(url=url, headers=headers, content=content)
            return types.SimpleNamespace(status_code=200, content=b"grpc-response")

    monkeypatch.setattr(spot_request, "get_username", lambda: "user")
    monkeypatch.setattr(spot_request, "get_spot_token", lambda username: "token")
    monkeypatch.setattr(spot_request.GrpcParser, "construct_grpc", lambda payload: b"grpc-" + payload)
    monkeypatch.setattr(spot_request.GrpcParser, "extract_grpc_payload", lambda content: b"result")
    monkeypatch.setattr(spot_request.httpx, "Client", Client)

    assert spot_request.spot_request("Scope", b"payload") == b"result"
    assert captured["client_kwargs"] == {"http2": True, "timeout": 30.0}
    assert captured["url"].endswith(".SpotService/Scope")
    assert captured["headers"]["Authorization"] == "Bearer token"
    assert captured["content"] == b"grpc-payload"


def test_spot_request_error_returns_empty_and_prints(monkeypatch, capsys):
    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers, content):
            return types.SimpleNamespace(status_code=500, text="<html>bad</html>")

    monkeypatch.setattr(spot_request, "get_username", lambda: "user")
    monkeypatch.setattr(spot_request, "get_spot_token", lambda username: "token")
    monkeypatch.setattr(spot_request.httpx, "Client", Client)
    assert spot_request.spot_request("Scope", b"payload") == b""
    assert "bad" in capsys.readouterr().out


def test_get_eid_info_request_serializes_request_and_parses_response(monkeypatch):
    response = device_update_pb2.GetEidInfoForE2eeDevicesResponse()
    response.encryptedOwnerKeyAndMetadata.ownerKeyVersion = 7
    captured = {}

    def fake_spot(scope, payload):
        captured["scope"] = scope
        request = common_pb2.GetEidInfoForE2eeDevicesRequest()
        request.ParseFromString(payload)
        captured["request"] = request
        return response.SerializeToString()

    monkeypatch.setattr(get_eid_info_request, "spot_request", fake_spot)
    assert get_eid_info_request.get_eid_info() == response
    assert captured["scope"] == "get_eid_info_for_e2ee_devices"
    assert captured["request"].ownerKeyVersion == -1
    assert captured["request"].hasOwnerKeyVersion is True


def test_owner_key_retrieval_and_cache(monkeypatch):
    eid_info = types.SimpleNamespace(
        encryptedOwnerKeyAndMetadata=types.SimpleNamespace(encryptedOwnerKey=b"encrypted", ownerKeyVersion=3)
    )
    monkeypatch.setattr(get_owner_key, "get_eid_info", lambda: eid_info)
    monkeypatch.setattr(get_owner_key, "get_shared_key", lambda: b"shared")
    monkeypatch.setattr(get_owner_key, "decrypt_owner_key", lambda shared, encrypted: b"owner")
    assert get_owner_key._retrieve_owner_key() == "6f776e6572"
    monkeypatch.setattr(get_owner_key, "get_cached_value_or_set", lambda name, generator: "6f776e6572")
    assert get_owner_key.get_owner_key() == b"owner"
