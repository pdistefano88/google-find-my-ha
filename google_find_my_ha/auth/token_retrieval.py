#
#  GoogleFindMyTools - A set of tools to interact with the Google Find My API
#  Copyright © 2024 Leon Böttger. All rights reserved.
#

import gpsoauth

from google_find_my_ha.auth.aas_token_retrieval import get_aas_token
from google_find_my_ha.auth.fcm_receiver import FcmReceiver


def request_token(username: str, scope: str, play_services: bool=False) -> str:
    aas_token = get_aas_token()
    android_id = FcmReceiver().get_android_id()
    request_app = 'com.google.android.gms' if play_services else 'com.google.android.apps.adm'

    auth_response = gpsoauth.perform_oauth(
        username, aas_token, android_id,
        service='oauth2:https://www.googleapis.com/auth/' + scope,
        app=request_app,
        client_sig='38918a453d07199354f8b19af05ec6562ced5788')
    token = auth_response['Auth']

    return token
