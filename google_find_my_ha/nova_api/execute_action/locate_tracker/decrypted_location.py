#
#  GoogleFindMyTools - A set of tools to interact with the Google Find My API
#  Copyright © 2024 Leon Böttger. All rights reserved.
#
from typing import NamedTuple

from google_find_my_ha.proto_decoders import common_pb2


class WrappedLocation(NamedTuple):
    time: int
    status: common_pb2.Status
    decrypted_location: bytes
    is_own_report: bool
    accuracy: float
    name: str
