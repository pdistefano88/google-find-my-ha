from google_find_my_ha.ProtoDecoders import (
    Common_pb2,
    DeviceUpdate_pb2,
    LocationReportsUpload_pb2,
    decoder,
)
from google_find_my_ha.ProtoDecoders.decoder import custom_message_formatter, get_canonic_ids


def test_parse_protobuf_roundtrips():
    update = DeviceUpdate_pb2.DeviceUpdate()
    update.fcmMetadata.requestUuid = "req"
    assert decoder.parse_device_update_protobuf(update.SerializeToString().hex()) == update

    devices = DeviceUpdate_pb2.DevicesList()
    devices.deviceMetadata.add(userDefinedDeviceName="Tracker")
    assert decoder.parse_device_list_protobuf(devices.SerializeToString().hex()) == devices

    upload = LocationReportsUpload_pb2.LocationReportsUpload(random1=1)
    assert decoder.parse_location_report_upload_protobuf(upload.SerializeToString().hex()) == upload


def test_get_canonic_ids_handles_android_and_non_android_devices():
    devices = DeviceUpdate_pb2.DevicesList()
    android = devices.deviceMetadata.add(userDefinedDeviceName="Phone")
    android.identifierInformation.type = DeviceUpdate_pb2.IDENTIFIER_ANDROID
    android.identifierInformation.phoneInformation.canonicIds.canonicId.add(id="phone-id")
    tracker = devices.deviceMetadata.add(userDefinedDeviceName="Tracker")
    tracker.identifierInformation.type = DeviceUpdate_pb2.IDENTIFIER_SPOT
    tracker.identifierInformation.canonicIds.canonicId.add(id="tracker-id")

    assert get_canonic_ids(devices) == [("Phone", "phone-id"), ("Tracker", "tracker-id")]


def test_custom_formatter_formats_bytes_and_time():
    report = Common_pb2.LocationReport(status=Common_pb2.Status.LAST_KNOWN)
    report.geoLocation.encryptedReport.encryptedLocation = b"\x00\xff"
    formatted = custom_message_formatter(report, "0", False)
    assert 'encryptedLocation: "00ff"' in formatted
    assert "status: 1" in formatted
