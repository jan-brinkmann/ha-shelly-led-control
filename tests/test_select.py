"""Tests for LED indication selection and its dependent configuration entities."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shelly_led_control.api import ShellyUnsupportedDeviceError
from custom_components.shelly_led_control.const import DOMAIN

TEST_MAC = "aa:bb:cc:dd:ee:ff"

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def _setup_entry(hass, mock_client) -> MockConfigEntry:
    """Load a complete integration entry with a connected mocked client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Waschmaschine",
        unique_id=TEST_MAC,
        data={CONF_HOST: "192.0.2.10"},
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.shelly_led_control.ShellyLedClient", return_value=mock_client
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def _mode_entry(hass, config_entry) -> er.RegistryEntry:
    """Return the mode selector registered for the Shelly entry."""
    return next(
        item
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), config_entry.entry_id
        )
        if item.domain == "select"
    )


@pytest.fixture
async def config_entry(hass, mock_client) -> MockConfigEntry:
    """Return a loaded integration entry for each selector test."""
    return await _setup_entry(hass, mock_client)


@pytest.fixture
def mode_entry(hass, config_entry) -> er.RegistryEntry:
    """Return the loaded entry's mode selector."""
    return _mode_entry(hass, config_entry)


@pytest.mark.parametrize(
    ("language", "name"),
    [("en", "LED indication mode"), ("de", "LED-Anzeigemodus")],
)
async def test_mode_selector_metadata(
    hass, mock_client, language: str, name: str
) -> None:
    """Expose translated names, two options and stable device/registry metadata."""
    hass.config.language = language
    entry = await _setup_entry(hass, mock_client)
    selector = _mode_entry(hass, entry)
    state = hass.states.get(selector.entity_id)
    assert state.state == "power"
    assert state.attributes["options"] == ["power", "switch"]
    assert selector.original_name == name
    assert selector.unique_id == f"{TEST_MAC}_led_indication_mode"
    assert selector.entity_category is EntityCategory.CONFIG
    device = dr.async_get(hass).async_get(selector.device_id)
    assert device.identifiers == {(DOMAIN, TEST_MAC)}
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, TEST_MAC)}


@pytest.mark.parametrize("initial_mode", ["power", "switch", "off"])
@pytest.mark.parametrize("mode", ["power", "switch"])
async def test_selecting_mode_refreshes_dependent_entities(
    hass, mock_client, led_config, config_entry, mode_entry, initial_mode, mode
) -> None:
    """Select an enabled mode, preserve settings and update dimming/color controls."""
    led_config["leds"]["mode"] = initial_mode
    await config_entry.runtime_data.coordinator.async_refresh()
    original = deepcopy(led_config)

    async def set_mode(value: str) -> None:
        """Change only the mocked device's LED mode."""
        led_config["leds"]["mode"] = value

    mock_client.async_set_led_mode.side_effect = set_mode
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": mode_entry.entity_id, "option": mode},
        blocking=True,
    )
    mock_client.async_set_led_mode.assert_awaited_once_with(mode)
    assert hass.states.get(mode_entry.entity_id).state == mode
    entries = {
        item.translation_key: item
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), config_entry.entry_id
        )
    }
    assert float(hass.states.get(entries["normal_brightness"].entity_id).state) == (
        100 if mode == "power" else 80
    )
    assert hass.states.get(entries["status_led"].entity_id).state == "on"
    for key in ("switch_on_color", "switch_off_color"):
        assert hass.states.get(entries[key].entity_id).state == (
            "on" if mode == "switch" else "unavailable"
        )
    original["leds"]["mode"] = mode
    assert led_config == original


@pytest.mark.parametrize("mode", ["off", "unsupported"])
async def test_selector_has_no_option_while_disabled_or_unsupported(
    hass, led_config, config_entry, mode_entry, mode
) -> None:
    """Report no enabled mode while retaining the ability to choose one."""
    led_config["leds"]["mode"] = mode
    await config_entry.runtime_data.coordinator.async_refresh()
    assert hass.states.get(mode_entry.entity_id).state == "unknown"


async def test_selector_tracks_external_mode_changes(
    hass, led_config, config_entry, mode_entry
) -> None:
    """Update selection from web UI settings refreshed by the coordinator."""
    led_config["leds"]["mode"] = "switch"
    await config_entry.runtime_data.coordinator.async_refresh()
    assert hass.states.get(mode_entry.entity_id).state == "switch"


@pytest.mark.parametrize("mode", ["off", "invalid"])
async def test_invalid_option_is_rejected(hass, mock_client, mode_entry, mode) -> None:
    """Reject options outside power/switch before invoking the device client."""
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": mode_entry.entity_id, "option": mode},
            blocking=True,
        )
    mock_client.async_set_led_mode.assert_not_awaited()


@pytest.mark.parametrize(
    "error",
    [
        DeviceConnectionError("Disconnected"),
        InvalidAuthError("Invalid credentials"),
        RpcCallError(500, "Rejected"),
        ShellyUnsupportedDeviceError("Missing settings"),
        ValueError("Invalid mode"),
    ],
)
async def test_failed_mode_write_retains_previous_state(
    hass, mock_client, mode_entry, error
) -> None:
    """Surface device errors without optimistically changing the selected mode."""
    mock_client.async_set_led_mode.side_effect = error
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": mode_entry.entity_id, "option": "switch"},
            blocking=True,
        )
    assert hass.states.get(mode_entry.entity_id).state == "power"


async def test_disconnect_and_unload_stop_selector(
    hass, mock_client, config_entry, mode_entry
) -> None:
    """Mark selection unavailable on disconnect and restore its state on unload."""
    mock_client.connected = False
    config_entry.runtime_data.coordinator._async_handle_connection_change()
    await hass.async_block_till_done()
    assert hass.states.get(mode_entry.entity_id).state == "unavailable"
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(mode_entry.entity_id)
    assert state.state == "unavailable"
    assert state.attributes["restored"] is True
