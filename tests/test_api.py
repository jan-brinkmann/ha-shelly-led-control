"""Tests for Shelly RPC configuration updates."""

from copy import deepcopy
from datetime import time
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from custom_components.shelly_led_control.api import ShellyLedClient
from custom_components.shelly_led_control.const import RPC_TIMEOUT


@pytest.mark.asyncio
async def test_disabling_led_preserves_complete_configuration() -> None:
    """Disable only the LED mode while retaining all other device settings."""
    led_config = {
        "leds": {
            "mode": "power",
            "brightness": 100,
            "night_mode": {
                "enable": True,
                "brightness": 25,
                "active_between": ["22:00", "06:00"],
            },
        },
    }
    device = MagicMock()
    device.connected = True
    device.call_rpc = AsyncMock(side_effect=[deepcopy(led_config), {}])
    client = ShellyLedClient(MagicMock(), "192.0.2.10", None, None)
    client._device = device

    await client.async_set_led_enabled(False)

    expected_config = deepcopy(led_config)
    expected_config["leds"]["mode"] = "off"
    assert device.call_rpc.await_args_list == [
        call("PLUGS_UI.GetConfig", timeout=RPC_TIMEOUT),
        call("PLUGS_UI.SetConfig", {"config": expected_config}, timeout=RPC_TIMEOUT),
    ]


@pytest.mark.asyncio
async def test_enabling_led_uses_last_active_mode() -> None:
    """Restore the prior active LED mode rather than overwriting it."""
    led_config = {"leds": {"mode": "off", "brightness": 100}}
    device = MagicMock()
    device.connected = True
    device.call_rpc = AsyncMock(side_effect=[led_config, {}])
    client = ShellyLedClient(MagicMock(), "192.0.2.10", None, None)
    client._device = device
    client._last_enabled_mode = "power"

    await client.async_set_led_enabled(True)

    expected_config = deepcopy(led_config)
    expected_config["leds"]["mode"] = "power"
    assert device.call_rpc.await_args_list[-1] == call(
        "PLUGS_UI.SetConfig", {"config": expected_config}, timeout=RPC_TIMEOUT
    )


@pytest.mark.asyncio
async def test_getting_device_time_uses_the_shelly_local_clock() -> None:
    """Read the Shelly-local clock with seconds for exact boundary refreshes."""
    device = MagicMock()
    device.connected = True
    device.call_rpc = AsyncMock(return_value={"time": "22:15", "unixtime": 7})
    client = ShellyLedClient(MagicMock(), "192.0.2.10", None, None)
    client._device = device

    assert await client.async_get_device_time() == time(22, 15, 7)
    device.call_rpc.assert_awaited_once_with("Sys.GetStatus", timeout=RPC_TIMEOUT)


@pytest.mark.asyncio
async def test_enabling_night_mode_preserves_brightness_and_time_window() -> None:
    """Update only the night-mode enable flag in the Shelly configuration."""
    led_config = {
        "leds": {
            "mode": "power",
            "colors": {"power": {"brightness": 70}},
            "night_mode": {
                "enable": False,
                "brightness": 25,
                "active_between": ["22:00", "06:00"],
            },
        },
        "controls": {"switch:0": {"in_mode": "momentary"}},
    }
    device = MagicMock()
    device.connected = True
    device.call_rpc = AsyncMock(side_effect=[deepcopy(led_config), {}])
    client = ShellyLedClient(MagicMock(), "192.0.2.10", None, None)
    client._device = device

    await client.async_set_night_mode_enabled(True)

    expected_config = deepcopy(led_config)
    expected_config["leds"]["night_mode"]["enable"] = True
    assert device.call_rpc.await_args_list[-1] == call(
        "PLUGS_UI.SetConfig", {"config": expected_config}, timeout=RPC_TIMEOUT
    )


@pytest.mark.asyncio
async def test_updating_night_mode_start_preserves_other_settings() -> None:
    """Update only the requested night-mode window boundary."""
    led_config = {
        "leds": {
            "mode": "switch",
            "night_mode": {
                "enable": True,
                "brightness": 25,
                "active_between": ["22:00", "06:00"],
            },
        }
    }
    device = MagicMock()
    device.connected = True
    device.call_rpc = AsyncMock(side_effect=[deepcopy(led_config), {}])
    client = ShellyLedClient(MagicMock(), "192.0.2.10", None, None)
    client._device = device

    await client.async_set_night_mode_start(time(21, 30))

    expected_config = deepcopy(led_config)
    expected_config["leds"]["night_mode"]["active_between"] = ["21:30", "06:00"]
    assert device.call_rpc.await_args_list[-1] == call(
        "PLUGS_UI.SetConfig", {"config": expected_config}, timeout=RPC_TIMEOUT
    )
