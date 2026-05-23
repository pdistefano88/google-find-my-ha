import base64
import json
import sys

import pytest

from google_find_my_ha.KeyBackup import shared_key_request, shared_key_retrieval
from google_find_my_ha.KeyBackup.lskf_hasher import ascii_to_bytes
from google_find_my_ha.KeyBackup.response_parser import get_fmdn_shared_key
from google_find_my_ha.ProtoDecoders import DeviceUpdate_pb2


def test_security_domain_request_url_contains_expected_proto(monkeypatch):
    monkeypatch.setattr(shared_key_request, "generate_random_uuid", lambda: "session-id")
    url = shared_key_request.get_security_domain_request_url()

    assert url.startswith("https://accounts.google.com/encryption/unlock/android?kdi=")
    payload = base64.b64decode(url.split("kdi=", 1)[1])
    extras = DeviceUpdate_pb2.EncryptionUnlockRequestExtras()
    extras.ParseFromString(payload)
    assert extras.operation == 1
    assert extras.securityDomain.name == "finder_hw"
    assert extras.sessionId == "session-id"


def test_response_parser_returns_first_finder_hw_key():
    vault_keys = json.dumps({"finder_hw": [{"epoch": 1, "key": {"0": 1, "1": 255, "2": 3}}]})
    assert get_fmdn_shared_key(vault_keys) == bytearray([1, 255, 3])


def test_response_parser_raises_when_key_missing():
    with pytest.raises(Exception, match="No suitable key"):
        get_fmdn_shared_key(json.dumps({"other": []}))


def test_shared_key_retrieval_decodes_cached_hex(monkeypatch):
    monkeypatch.setattr(shared_key_retrieval, "get_cached_value_or_set", lambda name, generator: "00ff")
    assert shared_key_retrieval.get_shared_key() == b"\x00\xff"


def test_retrieve_shared_key_prompts_then_runs_flow(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    monkeypatch.setitem(
        sys.modules,
        "google_find_my_ha.KeyBackup.shared_key_flow",
        type("Flow", (), {"request_shared_key_flow": staticmethod(lambda: "abc")}),
    )
    assert shared_key_retrieval._retrieve_shared_key() == "abc"


def test_ascii_to_bytes_accepts_ascii_and_rejects_non_ascii():
    assert ascii_to_bytes("abc") == b"abc"
    with pytest.raises(UnicodeEncodeError):
        ascii_to_bytes("cafe é")
