import datetime

from google_find_my_ha.nova_api.execute_action.locate_tracker import decrypt_locations
from google_find_my_ha.proto_decoders import common_pb2, device_update_pb2


def make_update():
    return device_update_pb2.DeviceUpdate()


def test_is_mcu_tracker_checks_fast_pair_model_id():
    registration = device_update_pb2.DeviceRegistration(fastPairModelId=decrypt_locations.mcu_fast_pair_model_id)
    assert decrypt_locations.is_mcu_tracker(registration) is True
    registration.fastPairModelId = "other"
    assert decrypt_locations.is_mcu_tracker(registration) is False


def test_retrieve_identity_key_flips_mcu_data_and_decrypts(monkeypatch):
    registration = device_update_pb2.DeviceRegistration(fastPairModelId=decrypt_locations.mcu_fast_pair_model_id)
    registration.encryptedUserSecrets.encryptedIdentityKey = b"\x00\xff"
    monkeypatch.setattr(decrypt_locations, "get_owner_key", lambda: b"owner")
    calls = []
    monkeypatch.setattr(decrypt_locations, "decrypt_eik", lambda owner, data: calls.append((owner, data)) or b"identity")
    assert decrypt_locations.retrieve_identity_key(registration) == b"identity"
    assert calls == [(b"owner", b"\xff\x00")]


def test_decrypt_locations_returns_none_for_no_reports(monkeypatch):
    update = make_update()
    monkeypatch.setattr(decrypt_locations, "retrieve_identity_key", lambda registration: b"identity")
    assert decrypt_locations.decrypt_location_response_locations(update) is None


def test_decrypt_locations_returns_semantic_data(monkeypatch):
    update = make_update()
    reports = update.deviceMetadata.information.locationInformation.reports.recentLocationAndNetworkLocations
    loc = reports.networkLocations.add()
    loc.status = common_pb2.Status.SEMANTIC
    loc.semanticLocation.locationName = "Home"
    reports.networkLocationTimestamps.add(seconds=1700000000)
    monkeypatch.setattr(decrypt_locations, "retrieve_identity_key", lambda registration: b"identity")

    result = decrypt_locations.decrypt_location_response_locations(update)
    assert result == {
        "semantic_location": "Home",
        "timestamp": datetime.datetime.fromtimestamp(1700000000).strftime("%Y-%m-%d %H:%M:%S"),
        "status": common_pb2.Status.SEMANTIC,
        "is_own_report": True,
    }


def test_decrypt_locations_decrypts_own_geo_report(monkeypatch):
    update = make_update()
    reports = update.deviceMetadata.information.locationInformation.reports.recentLocationAndNetworkLocations
    loc = reports.networkLocations.add()
    loc.status = common_pb2.Status.LAST_KNOWN
    loc.geoLocation.accuracy = 3.5
    loc.geoLocation.encryptedReport.encryptedLocation = b"encrypted"
    loc.geoLocation.encryptedReport.isOwnReport = True
    reports.networkLocationTimestamps.add(seconds=1700000000)
    decrypted = device_update_pb2.Location(latitude=123456789, longitude=-987654321, altitude=42).SerializeToString()
    monkeypatch.setattr(decrypt_locations, "retrieve_identity_key", lambda registration: b"identity")
    monkeypatch.setattr(decrypt_locations, "decrypt_aes_gcm", lambda key, data: decrypted)

    result = decrypt_locations.decrypt_location_response_locations(update)
    assert result["latitude"] == 12.3456789
    assert result["longitude"] == -98.7654321
    assert result["altitude"] == 42
    assert result["accuracy"] == 3.5
    assert result["is_own_report"] is True


def test_decrypt_locations_decrypts_foreign_report_with_time_offset(monkeypatch):
    update = make_update()
    reports = update.deviceMetadata.information.locationInformation.reports.recentLocationAndNetworkLocations
    loc = reports.networkLocations.add()
    loc.status = common_pb2.Status.CROWDSOURCED
    loc.geoLocation.deviceTimeOffset = 123
    loc.geoLocation.encryptedReport.encryptedLocation = b"encrypted"
    loc.geoLocation.encryptedReport.publicKeyRandom = b"random"
    reports.networkLocationTimestamps.add(seconds=1700000000)
    decrypted = device_update_pb2.Location(latitude=1, longitude=2, altitude=3).SerializeToString()
    calls = []
    monkeypatch.setattr(decrypt_locations, "retrieve_identity_key", lambda registration: b"identity")
    monkeypatch.setattr(decrypt_locations, "decrypt", lambda *args: calls.append(args) or decrypted)

    result = decrypt_locations.decrypt_location_response_locations(update)
    assert calls == [(b"identity", b"encrypted", b"random", 123)]
    assert result["latitude"] == 0.0000001
