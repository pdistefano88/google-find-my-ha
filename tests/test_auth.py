import asyncio
import base64
import json
import sys
import types

import pytest

from google_find_my_ha.auth import (
    aas_token_retrieval,
    adm_token_retrieval,
    spot_token_retrieval,
    token_cache,
    token_retrieval,
    username_provider,
)


def test_token_cache_reads_writes_and_generates_once(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))

    calls = []

    assert token_cache.get_cached_value("missing") is None
    assert token_cache.get_cached_value_or_set("token", lambda: calls.append(1) or "abc") == "abc"
    assert token_cache.get_cached_value_or_set("token", lambda: calls.append(2) or "def") == "abc"
    assert calls == [1]
    assert json.loads((tmp_path / "secrets.json").read_text())["token"] == "abc"


def test_token_cache_invalid_json_gets_none_and_set_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRETS_DIR", str(tmp_path))
    (tmp_path / "secrets.json").write_text("not-json")

    assert token_cache.get_cached_value("anything") is None
    with pytest.raises(Exception, match="Could not read secrets file"):
        token_cache.set_cached_value("anything", "value")


def test_username_provider_returns_cached_or_empty(monkeypatch):
    monkeypatch.setattr(username_provider, "get_cached_value", lambda name: "user@example.com")
    assert username_provider.get_username() == "user@example.com"
    monkeypatch.setattr(username_provider, "get_cached_value", lambda name: None)
    assert username_provider.get_username() == ""


def test_token_retrieval_uses_scope_app_and_android_id(monkeypatch):
    calls = []

    monkeypatch.setattr(token_retrieval, "get_aas_token", lambda: "aas")
    monkeypatch.setattr(token_retrieval, "FcmReceiver", lambda: types.SimpleNamespace(get_android_id=lambda: "android"))
    monkeypatch.setattr(
        token_retrieval.gpsoauth,
        "perform_oauth",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {"Auth": "oauth"},
    )

    assert token_retrieval.request_token("user", "spot", play_services=True) == "oauth"
    args, kwargs = calls[0]
    assert args == ("user", "aas", "android")
    assert kwargs["service"] == "oauth2:https://www.googleapis.com/auth/spot"
    assert kwargs["app"] == "com.google.android.gms"


def test_aas_token_generation_caches_returned_email(monkeypatch):
    auth_flow = types.SimpleNamespace(request_oauth_account_token_flow=lambda: "account-token")
    monkeypatch.setitem(sys.modules, "google_find_my_ha.auth.auth_flow", auth_flow)
    monkeypatch.setattr(aas_token_retrieval, "get_username", lambda: "old@example.com")
    monkeypatch.setattr(aas_token_retrieval, "FcmReceiver", lambda: types.SimpleNamespace(get_android_id=lambda: "android"))
    monkeypatch.setattr(
        aas_token_retrieval.gpsoauth,
        "exchange_token",
        lambda username, token, android_id: {"Token": "aas", "Email": "new@example.com"},
    )
    cached = []
    monkeypatch.setattr(aas_token_retrieval, "set_cached_value", lambda name, value: cached.append((name, value)))

    assert aas_token_retrieval._generate_aas_token() == "aas"
    assert cached == [("username", "new@example.com")]


def test_get_aas_token_delegates_to_cache(monkeypatch):
    monkeypatch.setattr(aas_token_retrieval, "get_cached_value_or_set", lambda name, generator: (name, generator))
    name, generator = aas_token_retrieval.get_aas_token()
    assert name == "aas_token"
    assert generator is aas_token_retrieval._generate_aas_token


def test_adm_and_spot_tokens_delegate_with_expected_scopes(monkeypatch):
    adm_calls = []
    spot_calls = []
    monkeypatch.setattr(adm_token_retrieval, "request_token", lambda *args: adm_calls.append(args) or "adm")
    monkeypatch.setattr(spot_token_retrieval, "request_token", lambda *args: spot_calls.append(args) or "spot")

    assert adm_token_retrieval.get_adm_token("user") == "adm"
    assert spot_token_retrieval.get_spot_token("user") == "spot"
    assert adm_calls == [("user", "android_device_manager")]
    assert spot_calls == [("user", "spot", True)]


def test_fcm_receiver_handles_credentials_callbacks_and_payload(
    monkeypatch, reimport, fake_firebase_module
):
    monkeypatch.setattr("google_find_my_ha.auth.token_cache.get_cached_value", lambda name: None)
    cached = []
    monkeypatch.setattr("google_find_my_ha.auth.token_cache.set_cached_value", lambda name, value: cached.append((name, value)))
    module = reimport("google_find_my_ha.auth.fcm_receiver")
    module.FcmReceiver._instance = None
    receiver = module.FcmReceiver()
    seen = []

    receiver._on_credentials_updated({"fcm": "creds"})
    receiver.location_update_callbacks.append(seen.append)
    receiver._on_notification(
        {"data": {"com.google.android.apps.adm.FCM_PAYLOAD": base64.b64encode(b"abc").decode()}},
        None,
        None,
    )

    assert cached == [("fcm_credentials", {"fcm": "creds"})]
    assert seen == ["616263"]
    assert module.FcmReceiver() is receiver


def test_fcm_receiver_register_stop_and_android_id(monkeypatch, reimport, fake_firebase_module):
    monkeypatch.setattr("google_find_my_ha.auth.token_cache.get_cached_value", lambda name: {"gcm": {"android_id": "android"}, "fcm": {"registration": {"token": "token"}}})
    module = reimport("google_find_my_ha.auth.fcm_receiver")
    module.FcmReceiver._instance = None
    receiver = module.FcmReceiver()

    assert receiver.get_android_id() == "android"
    assert receiver.register_for_location_updates(lambda payload: payload, timeout_seconds=0) == "token"
    assert receiver.listening is True
    receiver.stop_listening()
    assert receiver.listening is False
    assert fake_firebase_module.created[-1].stopped is True


def test_fcm_timeout_handler_stops_listener(monkeypatch, reimport, fake_firebase_module):
    monkeypatch.setattr("google_find_my_ha.auth.token_cache.get_cached_value", lambda name: None)
    module = reimport("google_find_my_ha.auth.fcm_receiver")
    module.FcmReceiver._instance = None
    receiver = module.FcmReceiver()
    receiver._listening = True
    asyncio.run(receiver._timeout_handler(0))
    assert receiver.listening is False
