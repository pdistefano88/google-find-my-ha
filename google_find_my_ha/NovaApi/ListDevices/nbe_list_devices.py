#
#  GoogleFindMyTools - A set of tools to interact with the Google Find My API
#  Copyright © 2024 Leon Böttger. All rights reserved.
#

import binascii
import logging

from google_find_my_ha.NovaApi.nova_request import nova_request
from google_find_my_ha.NovaApi.scopes import NOVA_LIST_DEVICS_API_SCOPE
from google_find_my_ha.NovaApi.util import generate_random_uuid
from google_find_my_ha.ProtoDecoders import DeviceUpdate_pb2

logger = logging.getLogger(__name__)


def request_device_list() -> str:
    hex_payload = create_device_list_request()
    result = nova_request(NOVA_LIST_DEVICS_API_SCOPE, hex_payload)

    return result


def create_device_list_request() -> str:
    wrapper = DeviceUpdate_pb2.DevicesListRequest()

    # Query for Spot devices
    wrapper.deviceListRequestPayload.type = DeviceUpdate_pb2.DeviceType.SPOT_DEVICE

    # Set a random UUID as the request ID
    wrapper.deviceListRequestPayload.id = generate_random_uuid()

    # Serialize to binary string
    binary_payload = wrapper.SerializeToString()

    # Convert to hex string
    hex_payload = binascii.hexlify(binary_payload).decode('utf-8')

    return hex_payload
