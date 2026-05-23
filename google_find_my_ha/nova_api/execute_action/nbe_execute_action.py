#
#  GoogleFindMyTools - A set of tools to interact with the Google Find My API
#  Copyright © 2024 Leon Böttger. All rights reserved.
#

import binascii

from google_find_my_ha.nova_api.util import generate_random_uuid
from google_find_my_ha.proto_decoders import device_update_pb2

# Generate a random, but fixed client ID for request identification for this session
client_id = generate_random_uuid()


def create_action_request(canonic_device_id: str,
                          gcm_registration_id: str,
                          request_uuid=generate_random_uuid(),
                          fmd_client_uuid: str=client_id) -> device_update_pb2.ExecuteActionRequest:
    action_request = device_update_pb2.ExecuteActionRequest()

    action_request.scope.type = device_update_pb2.DeviceType.SPOT_DEVICE
    action_request.scope.device.canonicId.id = canonic_device_id

    action_request.requestMetadata.type = device_update_pb2.DeviceType.SPOT_DEVICE
    action_request.requestMetadata.requestUuid = request_uuid

    action_request.requestMetadata.fmdClientUuid = fmd_client_uuid
    action_request.requestMetadata.gcmRegistrationId.id = gcm_registration_id
    action_request.requestMetadata.unknown = True

    return action_request


def serialize_action_request(actionRequest: device_update_pb2.ExecuteActionRequest) -> str:
    # Serialize to binary string
    binary_payload = actionRequest.SerializeToString()

    # Convert to hex string
    hex_payload = binascii.hexlify(binary_payload).decode('utf-8')

    return hex_payload
