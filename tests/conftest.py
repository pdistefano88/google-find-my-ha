import importlib
import sys
import types

import pytest


@pytest.fixture
def reimport():
    def load(module_name):
        sys.modules.pop(module_name, None)
        return importlib.import_module(module_name)

    return load


@pytest.fixture
def fake_firebase_module(monkeypatch):
    created = []

    class FakeConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakePushClient:
        def __init__(self, on_notification, config, credentials, on_credentials_updated):
            self.on_notification = on_notification
            self.config = config
            self.credentials = credentials
            self.on_credentials_updated = on_credentials_updated
            self.stopped = False
            self.started = False
            self.checkins = 0
            created.append(self)

        async def checkin_or_register(self):
            self.checkins += 1
            return "fcm-token"

        async def start(self):
            self.started = True

        async def stop(self):
            self.stopped = True

    module = types.SimpleNamespace(
        FcmPushClient=FakePushClient,
        FcmRegisterConfig=FakeConfig,
        created=created,
    )
    monkeypatch.setitem(sys.modules, "firebase_messaging", module)
    return module


@pytest.fixture
def fake_chromedriver_module(monkeypatch):
    created = []

    class FakeOptions:
        def __init__(self):
            self.arguments = []
            self.binary_location = None

        def add_argument(self, argument):
            self.arguments.append(argument)

    class FakeUc:
        ChromeOptions = FakeOptions

        def __init__(self):
            self.failures = []

        def Chrome(self, options=None):
            created.append(options)
            if self.failures:
                raise self.failures.pop(0)
            return types.SimpleNamespace(options=options)

    uc = FakeUc()
    uc.created = created
    monkeypatch.setitem(sys.modules, "undetected_chromedriver", uc)
    return uc


class DummyPublishResult:
    def __init__(self):
        self.waited = False

    def wait_for_publish(self):
        self.waited = True



class DummyMqttClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, retain=False):
        result = DummyPublishResult()
        self.published.append((topic, payload, retain, result))
        return result
