#
#  GoogleFindMyTools - A set of tools to interact with the Google Find My API
#  Copyright © 2024 Leon Böttger. All rights reserved.
#
from google_find_my_ha.proto_decoders import common_pb2
from google_find_my_ha.proto_decoders import device_update_pb2
from google_find_my_ha.spot_api.spot_request import spot_request

def get_eid_info():
    get_eid_info_for_e2ee_devices_request = common_pb2.GetEidInfoForE2eeDevicesRequest()
    get_eid_info_for_e2ee_devices_request.ownerKeyVersion = -1
    get_eid_info_for_e2ee_devices_request.hasOwnerKeyVersion = True

    serialized_request = get_eid_info_for_e2ee_devices_request.SerializeToString()
    response_bytes = spot_request("get_eid_info_for_e2ee_devices", serialized_request)

    eid_info = device_update_pb2.GetEidInfoForE2eeDevicesResponse()
    eid_info.ParseFromString(response_bytes)

    return eid_info


if __name__ == '__main__':
    print(get_eid_info().encryptedOwnerKeyAndMetadata)
