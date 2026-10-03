"""Tests for Shelly RPC configuration updates."""

from copy import deepcopy
from datetime import time
from unittest.mock import AsyncMock, MagicMock, call

import pytest
from aioshelly.rpc_device import RpcUpdateType

from custom_components.shelly_led_control.api import (
    ShellyLedClient,
    ShellyUnsupportedDeviceError,
    led_brightness_from_config,
)
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


@pytest.mark.asyncio
@pytest.mark.parametrize("brightness", [0, 1, 42.5, 100])
@pytest.mark.parametrize("enabled", [False, True])
async def test_updating_night_mode_brightness_preserves_other_settings(
    brightness: float, enabled: bool
) -> None:
    """Change only brightness, including zero, without mutating the read config."""
    led_config = {
        "leds": {
            "mode": "power",
            "colors": {
                "switch:0": {
                    "on": {"rgb": [0, 100, 0], "brightness": 80},
                    "off": {"rgb": [100, 0, 0], "brightness": 60},
                },
                "power": {"brightness": 70},
            },
            "night_mode": {
                "enable": enabled,
                "brightness": 25,
                "active_between": ["22:00", "06:00"],
            },
        },
        "controls": {"switch:0": {"in_mode": "momentary"}},
    }
    original_config = deepcopy(led_config)
    device = MagicMock()
    device.connected = True
    device.call_rpc = AsyncMock(side_effect=[led_config, {}])
    client = ShellyLedClient(MagicMock(), "192.0.2.10", None, None)
    client._device = device

    await client.async_set_night_mode_brightness(brightness)

    expected_config = deepcopy(original_config)
    expected_config["leds"]["night_mode"]["brightness"] = brightness
    assert device.call_rpc.await_args_list == [
        call("PLUGS_UI.GetConfig", timeout=RPC_TIMEOUT),
        call("PLUGS_UI.SetConfig", {"config": expected_config}, timeout=RPC_TIMEOUT),
    ]
    assert led_config == original_config


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "output"), [("power", None), ("switch", True), ("switch", False)]
)
@pytest.mark.parametrize("brightness", [0, 42.5, 100])
@pytest.mark.parametrize("missing_brightness", [False, True])
async def test_updating_normal_brightness_preserves_other_settings(
    led_config: dict,
    mode: str,
    output: bool | None,
    brightness: float,
    missing_brightness: bool,
) -> None:
    """Write only the current branch, reading fresh relay output in switch mode."""
    led_config["leds"]["mode"] = mode
    led_config["controls"] = {"switch:0": {"in_mode": "detached"}}
    branch = (
        led_config["leds"]["colors"]["power"]
        if mode == "power"
        else led_config["leds"]["colors"]["switch:0"]["on" if output else "off"]
    )
    if missing_brightness:
        del branch["brightness"]
    original_config = deepcopy(led_config)
    responses = [led_config]
    if mode == "switch":
        responses.append({"output": output})
    responses.append({})
    device = MagicMock()
    device.connected = True
    device.call_rpc = AsyncMock(side_effect=responses)
    client = ShellyLedClient(MagicMock(), "192.0.2.10", None, None)
    client._device = device
    client._last_switch_output = not output

    await client.async_set_led_brightness(brightness)

    expected_config = deepcopy(original_config)
    expected_branch = (
        expected_config["leds"]["colors"]["power"]
        if mode == "power"
        else expected_config["leds"]["colors"]["switch:0"]["on" if output else "off"]
    )
    expected_branch["brightness"] = brightness
    expected_calls = [call("PLUGS_UI.GetConfig", timeout=RPC_TIMEOUT)]
    if mode == "switch":
        expected_calls.append(call("Switch.GetStatus", {"id": 0}, timeout=RPC_TIMEOUT))
    expected_calls.append(
        call("PLUGS_UI.SetConfig", {"config": expected_config}, timeout=RPC_TIMEOUT)
    )
    assert device.call_rpc.await_args_list == expected_calls
    assert led_config == original_config


@pytest.mark.parametrize(
    ("config", "output"),
    [
        ({"leds": {"mode": "off"}}, True),
        ({"leds": {"mode": "unsupported"}}, True),
        ({"leds": {"mode": "power"}}, True),
        ({"leds": {"mode": "power", "colors": []}}, True),
        ({"leds": {"mode": "power", "colors": {"power": None}}}, True),
        ({"leds": {"mode": "switch", "colors": {"switch:0": None}}}, True),
        ({"leds": {"mode": "switch", "colors": {"switch:0": {"on": None}}}}, True),
        ({"leds": {"mode": "switch", "colors": {"switch:0": {"on": {}}}}}, None),
        ({"leds": {"mode": "switch", "colors": {"switch:0": {"on": {}}}}}, 1),
    ],
)
async def test_unselectable_normal_brightness_is_not_written(
    config: dict, output: object
) -> None:
    """Reject disabled modes and unknown or malformed targets without a write."""
    device = MagicMock()
    device.connected = True
    device.call_rpc = AsyncMock(side_effect=[config, {"output": output}])
    client = ShellyLedClient(MagicMock(), "192.0.2.10", None, None)
    client._device = device

    with pytest.raises(ShellyUnsupportedDeviceError):
        await client.async_set_led_brightness(50)

    assert all(
        item.args[0] != "PLUGS_UI.SetConfig" for item in device.call_rpc.await_args_list
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method_name", ["async_set_led_brightness", "async_set_night_mode_brightness"]
)
@pytest.mark.parametrize(
    "brightness", [-1, 101, float("nan"), float("inf"), -float("inf"), True, "25", None]
)
async def test_invalid_brightness_does_not_contact_device(
    brightness: object, method_name: str
) -> None:
    """Reject invalid percentages before reading or writing device settings."""
    device = MagicMock()
    device.connected = True
    device.call_rpc = AsyncMock()
    client = ShellyLedClient(MagicMock(), "192.0.2.10", None, None)
    client._device = device

    with pytest.raises(ValueError, match="brightness must be between 0 and 100"):
        await getattr(client, method_name)(brightness)

    device.call_rpc.assert_not_awaited()


@pytest.mark.parametrize(
    ("mode", "output", "expected"),
    [
        ("power", None, 100),
        ("switch", True, 80),
        ("switch", False, 40),
        ("switch", None, None),
        ("off", None, 0),
        ("unsupported", True, None),
    ],
)
def test_normal_brightness_uses_mode_and_output(
    led_config: dict, mode: str, output: bool | None, expected: float | None
) -> None:
    """Read the correct normal brightness branch without mutating settings."""
    led_config["leds"]["mode"] = mode
    original = deepcopy(led_config)

    assert led_brightness_from_config(led_config, output) == expected
    assert led_config == original


@pytest.mark.parametrize(
    "brightness", [-1, 101, float("nan"), float("inf"), True, "25", None]
)
def test_invalid_normal_brightness_is_unknown(
    led_config: dict, brightness: object
) -> None:
    """Do not expose malformed percentages or fail unrelated entity updates."""
    led_config["leds"]["colors"]["power"]["brightness"] = brightness

    assert led_brightness_from_config(led_config, None) is None


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"leds": None},
        {"leds": {"mode": "power"}},
        {"leds": {"mode": "power", "colors": []}},
        {"leds": {"mode": "power", "colors": {"power": None}}},
        {"leds": {"mode": "switch", "colors": {"switch:0": None}}},
        {"leds": {"mode": "switch", "colors": {"switch:0": {"on": None}}}},
    ],
)
def test_missing_normal_brightness_is_unknown(config: dict) -> None:
    """Treat incomplete or malformed optional brightness branches as unknown."""
    assert led_brightness_from_config(config, True) is None


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ({"output": True}, True),
        ({"output": False}, False),
        ({}, None),
        ({"output": 1}, None),
        ({"output": "false"}, None),
        (None, None),
    ],
)
async def test_reading_switch_output(status: object, expected: bool | None) -> None:
    """Fetch relay output for periodic recovery, preserving unknown status."""
    device = MagicMock()
    device.connected = True
    device.call_rpc = AsyncMock(return_value=status)
    client = ShellyLedClient(MagicMock(), "192.0.2.10", None, None)
    client._device = device

    assert await client.async_get_switch_output() is expected
    device.call_rpc.assert_awaited_once_with(
        "Switch.GetStatus", {"id": 0}, timeout=RPC_TIMEOUT
    )


async def test_relay_push_ignores_unchanged_output(hass) -> None:
    """Refresh after relay output changes, ignoring unrelated power readings."""
    device = MagicMock()
    device.connected = True
    device.status = {"switch:0": {"output": True, "apower": 10}}
    device.call_rpc = AsyncMock(return_value={"output": True})
    client = ShellyLedClient(hass, "192.0.2.10", None, None)
    client._device = device
    refresh = AsyncMock()
    availability = MagicMock()
    client.async_set_callbacks(refresh, availability)
    await client.async_get_switch_output()

    client._async_handle_rpc_update(device, RpcUpdateType.STATUS)
    device.status["switch:0"]["apower"] = 20
    client._async_handle_rpc_update(device, RpcUpdateType.STATUS)
    await hass.async_block_till_done()
    refresh.assert_not_awaited()

    device.status["switch:0"]["output"] = False
    client._async_handle_rpc_update(device, RpcUpdateType.STATUS)
    await hass.async_block_till_done()
    refresh.assert_awaited_once()
    availability.assert_not_called()
