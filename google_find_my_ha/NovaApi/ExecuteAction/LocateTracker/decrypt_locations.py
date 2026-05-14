#
#  GoogleFindMyTools - A set of tools to interact with the Google Find My API
#  Copyright © 2024 Leon Böttger. All rights reserved.
#

import datetime
import hashlib
import logging
from typing import TypedDict

from google_find_my_ha.FMDNCrypto.foreign_tracker_cryptor import decrypt
from google_find_my_ha.KeyBackup.cloud_key_decryptor import decrypt_aes_gcm, decrypt_eik
from google_find_my_ha.NovaApi.ExecuteAction.LocateTracker.decrypted_location import (
    WrappedLocation,
)
from google_find_my_ha.NovaApi.util import flip_bits
from google_find_my_ha.ProtoDecoders import Common_pb2, DeviceUpdate_pb2
from google_find_my_ha.ProtoDecoders.DeviceUpdate_pb2 import DeviceRegistration
from google_find_my_ha.SpotApi.GetEidInfoForE2eeDevices.get_eid_info_request import (
    get_eid_info,
)
from google_find_my_ha.SpotApi.GetEidInfoForE2eeDevices.get_owner_key import (
    get_owner_key,
)

mcu_fast_pair_model_id = "003200"

logger = logging.getLogger(__name__)


class LocationData(TypedDict):
    latitude: float
    longitude: float
    altitude: float
    accuracy: float
    timestamp: str
    status: Common_pb2.Status
    is_own_report: bool


class SemanticData(TypedDict):
    semantic_location: str
    timestamp: str
    status: Common_pb2.Status
    is_own_report: bool


# Indicates if the device is a custom microcontroller
def is_mcu_tracker(device_registration: DeviceRegistration) -> bool:
    return device_registration.fastPairModelId == mcu_fast_pair_model_id


def retrieve_identity_key(device_registration: DeviceRegistration) -> bytes:
    is_mcu = is_mcu_tracker(device_registration)
    encrypted_user_secrets = device_registration.encryptedUserSecrets

    encrypted_identity_key = flip_bits(
        encrypted_user_secrets.encryptedIdentityKey, is_mcu
    )
    owner_key = get_owner_key()

    try:
        identity_key = decrypt_eik(owner_key, encrypted_identity_key)
        return identity_key
    except Exception as e:
        e2eeData = get_eid_info()
        current_owner_key_version = (
            e2eeData.encryptedOwnerKeyAndMetadata.ownerKeyVersion
        )

        if encrypted_user_secrets.ownerKeyVersion < current_owner_key_version:
            logger.exception(
                f"Failed to decrypt E2EE data. This tracker was encrypted with owner key version {encrypted_user_secrets.ownerKeyVersion}, but the current owner key version is {current_owner_key_version}.\nThis happens if you reset your end-to-end-encrypted data in the past.\nThe tracker cannot be decrypted anymore, and it is recommended to remove it in the Find My Device app."
            )
            raise e
        else:
            logger.exception(
                f"Failed to decrypt identity key encrypted with owner key version {encrypted_user_secrets.ownerKeyVersion}, current owner key version is {current_owner_key_version}.\nThis may happen if you reset your end-to-end-encrypted data. To resolve this issue, open the folder 'Auth' and delete the file 'secrets.json'."
            )
            raise e


def decrypt_location_response_locations(
    device_update_protobuf: DeviceUpdate_pb2.DeviceUpdate,
) -> LocationData | SemanticData:
    device_registration = (
        device_update_protobuf.deviceMetadata.information.deviceRegistration
    )

    identity_key = retrieve_identity_key(device_registration)
    locations_proto = device_update_protobuf.deviceMetadata.information.locationInformation.reports.recentLocationAndNetworkLocations
    is_mcu = is_mcu_tracker(device_registration)

    # At All Areas Reports or Own Reports
    recent_location = locations_proto.recentLocation
    recent_location_time = locations_proto.recentLocationTimestamp

    # High Traffic Reports
    network_locations = list(locations_proto.networkLocations)
    network_locations_time = list(locations_proto.networkLocationTimestamps)

    if locations_proto.HasField("recentLocation"):
        network_locations.append(recent_location)
        network_locations_time.append(recent_location_time)

    location_time_array = []
    for loc, time in zip(network_locations, network_locations_time):
        if loc.status == Common_pb2.Status.SEMANTIC:
            logger.debug("Semantic Location Report")

            wrapped_location = WrappedLocation(
                decrypted_location=b"",
                time=int(time.seconds),
                accuracy=0,
                status=loc.status,
                is_own_report=True,
                name=loc.semanticLocation.locationName,
            )
            location_time_array.append(wrapped_location)
        else:
            encrypted_location = loc.geoLocation.encryptedReport.encryptedLocation
            public_key_random = loc.geoLocation.encryptedReport.publicKeyRandom

            if public_key_random == b"":  # Own Report
                identity_key_hash = hashlib.sha256(identity_key).digest()
                decrypted_location = decrypt_aes_gcm(
                    identity_key_hash, encrypted_location
                )
            else:
                time_offset = 0 if is_mcu else loc.geoLocation.deviceTimeOffset
                decrypted_location = decrypt(
                    identity_key, encrypted_location, public_key_random, time_offset
                )

            wrapped_location = WrappedLocation(
                decrypted_location=decrypted_location,
                time=int(time.seconds),
                accuracy=loc.geoLocation.accuracy,
                status=loc.status,
                is_own_report=loc.geoLocation.encryptedReport.isOwnReport,
                name="",
            )
            location_time_array.append(wrapped_location)

    logger.debug("[DecryptLocations] Decrypted Locations:")

    if not location_time_array:
        logger.debug("No locations found.")
        return None

    # Return data from the most recent location
    loc = location_time_array[0]

    if loc.status == Common_pb2.Status.SEMANTIC:
        logger.debug(f"Semantic Location: {loc.name}")
        location_data = {
            "semantic_location": loc.name,
            "timestamp": datetime.datetime.fromtimestamp(loc.time).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "status": loc.status,
            "is_own_report": loc.is_own_report,
        }
    else:
        proto_loc = DeviceUpdate_pb2.Location()
        proto_loc.ParseFromString(loc.decrypted_location)

        latitude = proto_loc.latitude / 1e7
        longitude = proto_loc.longitude / 1e7
        altitude = proto_loc.altitude

        logger.debug(f"Latitude: {latitude}")
        logger.debug(f"Longitude: {longitude}")
        logger.debug(f"Altitude: {altitude}")
        logger.debug(
            f"Time: {datetime.datetime.fromtimestamp(loc.time).strftime('%Y-%m-%d %H:%M:%S')}"
        )
        logger.debug(f"Status: {loc.status}")
        logger.debug(f"Is Own Report: {loc.is_own_report}")

        location_data = LocationData(
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            accuracy=loc.accuracy,
            timestamp=datetime.datetime.fromtimestamp(loc.time).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            status=loc.status,
            is_own_report=loc.is_own_report,
        )

    return location_data
