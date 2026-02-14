#
#  GoogleFindMyTools - A set of tools to interact with the Google Find My API
#  Copyright © 2024 Leon Böttger. All rights reserved.
#

import asyncio
import time
import logging

from google_find_my_ha.Auth.fcm_receiver import FcmReceiver
from google_find_my_ha.NovaApi.ExecuteAction.LocateTracker.decrypt_locations import decrypt_location_response_locations, LocationData
from google_find_my_ha.NovaApi.ExecuteAction.nbe_execute_action import create_action_request, serialize_action_request
from google_find_my_ha.NovaApi.nova_request import nova_request
from google_find_my_ha.NovaApi.scopes import NOVA_ACTION_API_SCOPE
from google_find_my_ha.NovaApi.util import generate_random_uuid
from google_find_my_ha.ProtoDecoders import DeviceUpdate_pb2
from google_find_my_ha.ProtoDecoders.decoder import parse_device_update_protobuf

logger = logging.getLogger(__name__)
TIMEOUT = 120


def create_location_request(canonic_device_id: str,
                            fcm_registration_id: str,
                            request_uuid: str) -> str:
    action_request = create_action_request(canonic_device_id, fcm_registration_id, request_uuid=request_uuid)

    # Random values, can be arbitrary
    action_request.action.locateTracker.lastHighTrafficEnablingTime.seconds = 1732120060
    action_request.action.locateTracker.contributorType = DeviceUpdate_pb2.SpotContributorType.FMDN_ALL_LOCATIONS

    # Convert to hex string
    hex_payload = serialize_action_request(action_request)

    return hex_payload


def get_location_data_for_device(canonic_device_id: str, name: str) -> LocationData:
    logger.debug(f"[LocationRequest] Requesting location data for {name}...")

    result = None
    request_uuid = generate_random_uuid()

    def handle_location_response(response):
        nonlocal result
        device_update = parse_device_update_protobuf(response)

        if device_update.fcmMetadata.requestUuid == request_uuid:
            logger.debug("[LocationRequest] Location request successful. Decrypting locations...")
            result = parse_device_update_protobuf(response)

    receiver = FcmReceiver()

    fcm_token = FcmReceiver().register_for_location_updates(handle_location_response)

    hex_payload = create_location_request(canonic_device_id, fcm_token, request_uuid)
    nova_request(NOVA_ACTION_API_SCOPE, hex_payload)

    while (result is None) and receiver.listening:
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.1))

    if result is None:
        raise TimeoutError("The FCM server timed out.")

    locations = decrypt_location_response_locations(result)
    return locations
