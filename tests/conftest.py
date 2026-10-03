"""Shared fixtures for Shelly Status LED Control tests."""

from copy import deepcopy
from datetime import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.shelly_led_control.api import ShellyDeviceInfo

TEST_MAC = "aa:bb:cc:dd:ee:ff"
TEST_LED_CONFIG = {
    "leds": {
        "mode": "power",
        "colors": {
            "switch:0": {
                "on": {"rgb": [0, 100, 0], "brightness": 80},
                "off": {"rgb": [100, 0, 0], "brightness": 40},
            },
            "power": {"brightness": 100},
        },
        "night_mode": {
            "enable": True,
            "brightness": 25,
            "active_between": ["22:00", "06:00"],
        },
    },
}


@pytest.fixture
def device_info() -> ShellyDeviceInfo:
    """Return metadata for a representative Shelly Plus Plug S."""
    return ShellyDeviceInfo(
        mac=TEST_MAC,
        model="SNSW-001P16EU",
        name="Waschmaschine",
        firmware_version="1.6.1",
    )


@pytest.fixture
def led_config() -> dict:
    """Return mutable device settings isolated from other tests."""
    return deepcopy(TEST_LED_CONFIG)


@pytest.fixture
def mock_client(device_info: ShellyDeviceInfo, led_config: dict) -> MagicMock:
    """Return a connected Shelly client that reads the mutable test settings."""
    client = MagicMock()
    client.connected = True
    client.async_connect = AsyncMock(return_value=device_info)
    client.async_disconnect = AsyncMock()
    client.async_get_led_config = AsyncMock(side_effect=lambda: deepcopy(led_config))
    client.async_get_device_time = AsyncMock(return_value=time(12, 0))
    client.async_get_switch_output = AsyncMock(return_value=True)
    client.async_set_led_enabled = AsyncMock()
    client.async_set_led_brightness = AsyncMock()
    client.async_set_night_mode_enabled = AsyncMock()
    client.async_set_night_mode_brightness = AsyncMock()
    client.async_set_night_mode_start = AsyncMock()
    client.async_set_night_mode_end = AsyncMock()
    return client
