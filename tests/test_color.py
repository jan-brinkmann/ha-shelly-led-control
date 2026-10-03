"""Exercise LED presets and dimming through Home Assistant and the RPC client."""

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
from aioshelly.rpc_device import RpcUpdateType
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shelly_led_control.api import ShellyLedClient
from custom_components.shelly_led_control.const import DOMAIN

TEST_MAC = "aa:bb:cc:dd:ee:ff"

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture
def rpc_device(led_config) -> MagicMock:
    """Emulate mutable Shelly settings while using the real integration client."""
    led_config["leds"]["mode"] = "switch"
    led_config["controls"] = {"switch:0": {"in_mode": "detached"}}
    device = MagicMock()
    device.connected = True
    device.config = led_config
    device.output = True
    device.clock = "12:00"
    device.status = {"sys": {"cfg_rev": 1}, "switch:0": {"output": True}}
    device.event = None
    device.shutdown = AsyncMock()

    async def call_rpc(method: str, params=None, **kwargs):
        """Read/write complete configurations and reject unimplemented RPC calls."""
        del kwargs
        if method == "PLUGS_UI.GetConfig":
            return deepcopy(device.config)
        if method == "PLUGS_UI.SetConfig":
            device.config.clear()
            device.config.update(deepcopy(params["config"]))
            return {"restart_required": False}
        if method == "Sys.GetStatus":
            return {"time": device.clock, "unixtime": 0}
        if method == "Switch.GetStatus":
            return {"output": device.output}
        raise AssertionError(f"Unexpected Shelly RPC method: {method}")

    device.call_rpc = AsyncMock(side_effect=call_rpc)
    return device


async def _setup_entry(hass, rpc_device, device_info) -> MockConfigEntry:
    """Load the real coordinator and client with the emulated RPC transport."""
    client = ShellyLedClient(hass, "192.0.2.10", None, None)
    client._device = rpc_device
    client.async_connect = AsyncMock(return_value=device_info)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Waschmaschine",
        unique_id=TEST_MAC,
        data={CONF_HOST: "192.0.2.10"},
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.shelly_led_control.ShellyLedClient", return_value=client
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


@pytest.fixture
async def config_entry(hass, rpc_device, device_info) -> MockConfigEntry:
    """Return a loaded entry with mutable RPC transport settings."""
    return await _setup_entry(hass, rpc_device, device_info)


def _entries(hass, entry) -> dict[str, er.RegistryEntry]:
    """Map each registered configuration or status entity by translation key."""
    return {
        item.translation_key: item
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }


@pytest.mark.parametrize(
    ("language", "names"),
    [
        ("en", ("LED color when relay is on", "LED color when relay is off")),
        ("de", ("LED-Farbe bei Relais an", "LED-Farbe bei Relais aus")),
    ],
)
async def test_color_preset_metadata(hass, rpc_device, device_info, language, names):
    """Expose two translated RGB configuration lights on the integration device."""
    hass.config.language = language
    entry = await _setup_entry(hass, rpc_device, device_info)
    entries = _entries(hass, entry)
    for key, name, rgb, brightness in (
        ("switch_on_color", names[0], (0, 255, 0), 204),
        ("switch_off_color", names[1], (255, 0, 0), 102),
    ):
        preset = entries[key]
        state = hass.states.get(preset.entity_id)
        assert state.state == "on"
        assert state.attributes["rgb_color"] == rgb
        assert state.attributes["brightness"] == brightness
        assert state.attributes["supported_color_modes"] == ["rgb"]
        assert preset.original_name == name
        assert preset.unique_id == f"{TEST_MAC}_{key}"
        assert preset.entity_category is EntityCategory.CONFIG
        assert preset.device_id == entries["status_led"].device_id
        device = dr.async_get(hass).async_get(preset.device_id)
        assert device.connections == {(dr.CONNECTION_NETWORK_MAC, TEST_MAC)}


@pytest.mark.parametrize("output", [True, False])
@pytest.mark.parametrize("rgb", [(255, 0, 0), (128, 64, 255), (0, 0, 0)])
async def test_color_service_changes_only_selected_rgb(
    hass, rpc_device, config_entry, output, rgb
) -> None:
    """Scale arbitrary RGB colors and preserve brightness, mode and other settings."""
    rpc_device.output = not output
    original = deepcopy(rpc_device.config)
    entries = _entries(hass, config_entry)
    key = "switch_on_color" if output else "switch_off_color"
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": entries[key].entity_id, "rgb_color": rgb},
        blocking=True,
    )
    expected = deepcopy(original)
    expected["leds"]["colors"]["switch:0"]["on" if output else "off"]["rgb"] = [
        round(value * 100 / 255, 2) for value in rgb
    ]
    assert rpc_device.config == expected
    assert hass.states.get(entries[key].entity_id).attributes["rgb_color"] == rgb
    assert rpc_device.output is not output


@pytest.mark.parametrize("output", [True, False])
async def test_combined_color_and_brightness_service(
    hass, rpc_device, config_entry, output
) -> None:
    """Apply color and dimming atomically and refresh the effective brightness."""
    rpc_device.output = output
    original = deepcopy(rpc_device.config)
    entries = _entries(hass, config_entry)
    key = "switch_on_color" if output else "switch_off_color"
    rpc_device.call_rpc.reset_mock()
    await hass.services.async_call(
        "light",
        "turn_on",
        {
            "entity_id": entries[key].entity_id,
            "rgb_color": [0, 0, 255],
            "brightness": 51,
        },
        blocking=True,
    )
    expected = deepcopy(original)
    expected["leds"]["colors"]["switch:0"]["on" if output else "off"].update(
        rgb=[0, 0, 100], brightness=20
    )
    assert rpc_device.config == expected
    assert hass.states.get(entries[key].entity_id).attributes["brightness"] == 51
    assert float(hass.states.get(entries["normal_brightness"].entity_id).state) == 20
    assert float(hass.states.get(entries["status_led_brightness"].entity_id).state) == (
        20
    )
    assert (
        sum(
            item.args[0] == "PLUGS_UI.SetConfig"
            for item in rpc_device.call_rpc.await_args_list
        )
        == 1
    )


@pytest.mark.parametrize("output", [True, False])
async def test_preset_off_and_bare_on_preserve_mode_and_colors(
    hass, rpc_device, config_entry, output
) -> None:
    """Disable only one preset and re-enable its brightness at 100 percent."""
    entries = _entries(hass, config_entry)
    key = "switch_on_color" if output else "switch_off_color"
    original = deepcopy(rpc_device.config)
    await hass.services.async_call(
        "light", "turn_off", {"entity_id": entries[key].entity_id}, blocking=True
    )
    expected = deepcopy(original)
    expected["leds"]["colors"]["switch:0"]["on" if output else "off"]["brightness"] = 0
    assert rpc_device.config == expected
    assert hass.states.get(entries[key].entity_id).state == "off"
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entries[key].entity_id}, blocking=True
    )
    settings = expected["leds"]["colors"]["switch:0"]["on" if output else "off"]
    settings["brightness"] = 100
    assert rpc_device.config == expected
    assert hass.states.get(entries[key].entity_id).state == "on"


@pytest.mark.parametrize(
    ("mode", "output"),
    [("power", True), ("power", False), ("switch", True), ("switch", False)],
)
@pytest.mark.parametrize("brightness", [0, 37, 100])
@pytest.mark.parametrize("night_active", [False, True])
async def test_normal_dimming_roundtrip_in_both_modes(
    hass, rpc_device, config_entry, mode, output, brightness, night_active
) -> None:
    """Verify actual RPC dimming in both modes with zero/full and night brightness."""
    entries = _entries(hass, config_entry)
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entries["led_indication_mode"].entity_id, "option": mode},
        blocking=True,
    )
    rpc_device.output = output
    rpc_device.clock = "23:00" if night_active else "12:00"
    original = deepcopy(rpc_device.config)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": entries["normal_brightness"].entity_id, "value": brightness},
        blocking=True,
    )
    expected = deepcopy(original)
    settings = (
        expected["leds"]["colors"]["power"]
        if mode == "power"
        else expected["leds"]["colors"]["switch:0"]["on" if output else "off"]
    )
    settings["brightness"] = brightness
    assert rpc_device.config == expected
    assert float(hass.states.get(entries["normal_brightness"].entity_id).state) == (
        brightness
    )
    effective = (
        0 if mode == "power" and output is False else 25 if night_active else brightness
    )
    assert float(hass.states.get(entries["status_led_brightness"].entity_id).state) == (
        effective
    )
    assert hass.states.get(entries["status_led"].entity_id).state == (
        "on" if effective > 0 else "off"
    )


@pytest.mark.parametrize("night_active", [False, True])
async def test_power_mode_relay_off_has_zero_effective_brightness(
    hass, rpc_device, device_info, night_active
) -> None:
    """Report a disabled power indicator as zero without changing its preset."""
    rpc_device.config["leds"]["mode"] = "power"
    rpc_device.output = False
    rpc_device.status["switch:0"]["output"] = False
    rpc_device.clock = "23:00" if night_active else "12:00"
    original = deepcopy(rpc_device.config)
    entry = await _setup_entry(hass, rpc_device, device_info)
    entries = _entries(hass, entry)

    assert float(hass.states.get(entries["status_led_brightness"].entity_id).state) == 0
    assert hass.states.get(entries["status_led"].entity_id).state == "off"
    assert hass.states.get(entries["night_mode_active"].entity_id).state == (
        "on" if night_active else "off"
    )
    assert float(hass.states.get(entries["normal_brightness"].entity_id).state) == 100
    assert hass.states.get(entries["led_indication_mode"].entity_id).state == "power"
    assert rpc_device.config == original
    assert all(
        item.args[0] != "PLUGS_UI.SetConfig"
        for item in rpc_device.call_rpc.await_args_list
    )


@pytest.mark.parametrize("initial_output", [True, False])
async def test_power_mode_relay_push_updates_sensor_and_status_light(
    hass, rpc_device, device_info, initial_output
) -> None:
    """Handle relay on/off pushes in power mode without waiting for fallback polls."""
    rpc_device.config["leds"]["mode"] = "power"
    rpc_device.output = initial_output
    rpc_device.status["switch:0"]["output"] = initial_output
    rpc_device.status["switch:0"]["apower"] = 0
    original = deepcopy(rpc_device.config)
    entry = await _setup_entry(hass, rpc_device, device_info)
    entries = _entries(hass, entry)
    assert float(hass.states.get(entries["status_led_brightness"].entity_id).state) == (
        100 if initial_output else 0
    )
    rpc_device.output = not initial_output
    rpc_device.status["switch:0"]["output"] = not initial_output
    entry.runtime_data.client._async_handle_rpc_update(rpc_device, RpcUpdateType.STATUS)
    await hass.async_block_till_done()

    assert float(hass.states.get(entries["status_led_brightness"].entity_id).state) == (
        0 if initial_output else 100
    )
    assert hass.states.get(entries["status_led"].entity_id).state == (
        "off" if initial_output else "on"
    )
    assert float(hass.states.get(entries["normal_brightness"].entity_id).state) == 100
    assert rpc_device.config == original


async def test_external_color_change_refreshes_without_brightness_or_relay_change(
    hass, rpc_device, config_entry
) -> None:
    """Publish color-only changes even when brightness and relay state stay equal."""
    entries = _entries(hass, config_entry)
    rpc_device.config["leds"]["colors"]["switch:0"]["off"]["rgb"] = [0, 0, 100]
    await config_entry.runtime_data.coordinator.async_refresh()
    assert hass.states.get(entries["switch_off_color"].entity_id).attributes[
        "rgb_color"
    ] == (0, 0, 255)


@pytest.mark.parametrize("output", [True, False])
@pytest.mark.parametrize("notification", ["plugs_ui", "PLUGS_UI", "cfg_rev"])
async def test_web_ui_color_notification_updates_preset(
    hass, rpc_device, config_entry, output, notification
) -> None:
    """Refresh web UI RGB changes from real notification shapes without polling."""
    entries = _entries(hass, config_entry)
    key = "switch_on_color" if output else "switch_off_color"
    original = deepcopy(rpc_device.config)
    rgb = [10, 50, 100]
    rpc_device.config["leds"]["colors"]["switch:0"]["on" if output else "off"][
        "rgb"
    ] = rgb
    rpc_device.call_rpc.reset_mock()
    client = config_entry.runtime_data.client
    if notification == "cfg_rev":
        rpc_device.status["sys"]["cfg_rev"] = 2
        client._async_handle_rpc_update(rpc_device, RpcUpdateType.STATUS)
    else:
        rpc_device.event = {
            "ts": 1000,
            "events": [
                {
                    "component": notification,
                    "event": "config_changed",
                    "cfg_rev": 2,
                    "restart_required": False,
                }
            ],
        }
        client._async_handle_rpc_update(rpc_device, RpcUpdateType.EVENT)
    await hass.async_block_till_done()

    state = hass.states.get(entries[key].entity_id)
    assert state.attributes["rgb_color"] == (26, 128, 255)
    assert state.attributes["brightness"] == (204 if output else 102)
    assert hass.states.get(entries["status_led"].entity_id).state == "on"
    original["leds"]["colors"]["switch:0"]["on" if output else "off"]["rgb"] = rgb
    assert rpc_device.config == original
    assert any(
        item.args[0] == "PLUGS_UI.GetConfig"
        for item in rpc_device.call_rpc.await_args_list
    )
    assert all(
        item.args[0] != "PLUGS_UI.SetConfig"
        for item in rpc_device.call_rpc.await_args_list
    )


@pytest.mark.parametrize("mode", ["power", "off", "unsupported"])
async def test_presets_unavailable_outside_switch_mode(
    hass, rpc_device, config_entry, mode
) -> None:
    """Reject color services while switch indication is inactive."""
    entries = _entries(hass, config_entry)
    rpc_device.config["leds"]["mode"] = mode
    await config_entry.runtime_data.coordinator.async_refresh()
    rpc_device.call_rpc.reset_mock()
    for key in ("switch_on_color", "switch_off_color"):
        assert hass.states.get(entries[key].entity_id).state == "unavailable"
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": entries[key].entity_id, "rgb_color": [255, 0, 0]},
            blocking=True,
        )
    rpc_device.call_rpc.assert_not_awaited()


@pytest.mark.parametrize(
    "error",
    [
        DeviceConnectionError("Disconnected"),
        InvalidAuthError("Invalid credentials"),
        RpcCallError(500, "Rejected"),
    ],
)
async def test_failed_color_write_keeps_previous_state(
    hass, rpc_device, config_entry, error
) -> None:
    """Surface RPC failures without publishing an unconfirmed color or brightness."""
    entries = _entries(hass, config_entry)
    original = deepcopy(rpc_device.config)
    rpc_device.call_rpc.side_effect = [deepcopy(original), error]
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "light",
            "turn_on",
            {
                "entity_id": entries["switch_on_color"].entity_id,
                "rgb_color": [0, 0, 255],
            },
            blocking=True,
        )
    assert rpc_device.config == original
    assert hass.states.get(entries["switch_on_color"].entity_id).attributes[
        "rgb_color"
    ] == (0, 255, 0)


async def test_disconnect_and_unload_stop_color_presets(
    hass, rpc_device, config_entry
) -> None:
    """Mark presets unavailable on disconnect and restore their states on unload."""
    entries = _entries(hass, config_entry)
    rpc_device.connected = False
    config_entry.runtime_data.coordinator._async_handle_connection_change()
    await hass.async_block_till_done()
    for key in ("switch_on_color", "switch_off_color"):
        assert hass.states.get(entries[key].entity_id).state == "unavailable"
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    for key in ("switch_on_color", "switch_off_color"):
        state = hass.states.get(entries[key].entity_id)
        assert state.state == "unavailable"
        assert state.attributes["restored"] is True
