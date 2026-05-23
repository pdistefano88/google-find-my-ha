import pytest


def test_find_chrome_prefers_known_existing_path(monkeypatch, reimport, fake_chromedriver_module):
    chrome_driver = reimport("chrome_driver")
    monkeypatch.setattr(chrome_driver.os.path, "exists", lambda path: path == "/usr/bin/google-chrome")
    assert chrome_driver.find_chrome() == "/usr/bin/google-chrome"


def test_find_chrome_falls_back_to_system_lookup(monkeypatch, reimport, fake_chromedriver_module):
    chrome_driver = reimport("chrome_driver")
    monkeypatch.setattr(chrome_driver.os.path, "exists", lambda path: False)
    monkeypatch.setattr(chrome_driver.platform, "system", lambda: "Linux")
    monkeypatch.setattr(chrome_driver.shutil, "which", lambda name: "/bin/chromium" if name == "chromium" else None)
    assert chrome_driver.find_chrome() == "/bin/chromium"


def test_get_options_sets_expected_arguments(reimport, fake_chromedriver_module):
    chrome_driver = reimport("chrome_driver")
    options = chrome_driver.get_options()
    assert options.arguments == [
        "--start-maximized",
        "--disable-extensions",
        "--disable-gpu",
        "--no-sandbox",
    ]


def test_create_driver_success_uses_default_options(reimport, fake_chromedriver_module):
    chrome_driver = reimport("chrome_driver")
    driver = chrome_driver.create_driver()
    assert driver.options.arguments[0] == "--start-maximized"
    assert driver.options.binary_location is None


def test_create_driver_falls_back_to_found_chrome(monkeypatch, reimport, fake_chromedriver_module):
    fake_chromedriver_module.failures = [RuntimeError("first failed")]
    chrome_driver = reimport("chrome_driver")
    monkeypatch.setattr(chrome_driver, "find_chrome", lambda: "/opt/chrome")
    driver = chrome_driver.create_driver()
    assert driver.options.binary_location == "/opt/chrome"


def test_create_driver_raises_when_all_paths_fail(monkeypatch, reimport, fake_chromedriver_module):
    fake_chromedriver_module.failures = [RuntimeError("first"), RuntimeError("second")]
    chrome_driver = reimport("chrome_driver")
    monkeypatch.setattr(chrome_driver, "find_chrome", lambda: "/opt/chrome")
    with pytest.raises(Exception, match="Failed to install ChromeDriver"):
        chrome_driver.create_driver()
