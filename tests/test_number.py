"""Tests for the night-mode brightness number and its device updates."""

from datetime import time
from unittest.mock import patch

import pytest
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.number.const import SERVICE_SET_VALUE
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
    """Load the integration with a mocked device and all entity platforms."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Waschmaschine",
        unique_id=TEST_MAC,
        data={CONF_HOST: "192.0.2.10"},
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.shelly_led_control.ShellyLedClient",
        return_value=mock_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


@pytest.fixture
async def config_entry(hass, mock_client) -> MockConfigEntry:
    """Return a loaded entry backed by the mock Shelly client."""
    return await _setup_entry(hass, mock_client)


@pytest.fixture
def number_entry(hass, config_entry) -> er.RegistryEntry:
    """Return the brightness entity registered for the configured Shelly."""
    return next(
        item
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), config_entry.entry_id
        )
        if item.domain == NUMBER_DOMAIN
    )


async def test_brightness_entity_metadata(hass, config_entry, number_entry) -> None:
    """Expose a configuration percentage with stable device and entity identity."""
    state = hass.states.get(number_entry.entity_id)
    assert float(state.state) == 25
    assert state.attributes["min"] == 0
    assert state.attributes["max"] == 100
    assert state.attributes["step"] == 1
    assert state.attributes["unit_of_measurement"] == "%"
    assert number_entry.unique_id == f"{TEST_MAC}_night_mode_brightness"
    assert number_entry.entity_category is EntityCategory.CONFIG
    device = dr.async_get(hass).async_get(number_entry.device_id)
    assert device.config_entries == {config_entry.entry_id}
    assert device.identifiers == {(DOMAIN, TEST_MAC)}
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, TEST_MAC)}


@pytest.mark.parametrize("initial_brightness", [0, 25])
@pytest.mark.parametrize("brightness", [0, 50, 100])
@pytest.mark.parametrize("enabled", [False, True])
async def test_setting_brightness_refreshes_number_and_light(
    hass,
    mock_client,
    led_config,
    brightness: float,
    enabled: bool,
    initial_brightness: float,
) -> None:
    """Refresh the configured percentage and effective LED state after a write."""
    config = led_config
    config["leds"]["night_mode"]["enable"] = enabled
    config["leds"]["night_mode"]["brightness"] = initial_brightness
    mock_client.async_get_device_time.return_value = time(23, 0)

    async def set_brightness(value: float) -> None:
        """Apply the mock device write so a refresh reads the new percentage."""
        config["leds"]["night_mode"]["brightness"] = value

    mock_client.async_set_night_mode_brightness.side_effect = set_brightness
    entry = await _setup_entry(hass, mock_client)
    entries = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    number = next(item for item in entries if item.domain == NUMBER_DOMAIN)
    light = next(item for item in entries if item.domain == "light")

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": number.entity_id, "value": brightness},
        blocking=True,
    )

    mock_client.async_set_night_mode_brightness.assert_awaited_once_with(brightness)
    assert float(hass.states.get(number.entity_id).state) == brightness
    expected_light_state = "off" if enabled and brightness == 0 else "on"
    assert hass.states.get(light.entity_id).state == expected_light_state
    assert config["leds"]["night_mode"]["enable"] is enabled
    assert config["leds"]["night_mode"]["active_between"] == ["22:00", "06:00"]
    assert mock_client.async_get_led_config.await_count == 2


async def test_external_brightness_change_updates_entity(
    hass, led_config, config_entry, number_entry
) -> None:
    """Read a percentage changed through the Shelly web UI on the next refresh."""
    led_config["leds"]["night_mode"]["brightness"] = 12.5

    await config_entry.runtime_data.coordinator.async_request_refresh()

    assert float(hass.states.get(number_entry.entity_id).state) == 12.5


async def test_missing_brightness_has_unknown_state(
    hass, mock_client, led_config
) -> None:
    """Keep setup working when the Shelly has not reported a brightness value."""
    del led_config["leds"]["night_mode"]["brightness"]
    entry = await _setup_entry(hass, mock_client)
    number = next(
        item
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if item.domain == NUMBER_DOMAIN
    )

    assert hass.states.get(number.entity_id).state == "unknown"


async def test_connection_loss_marks_brightness_unavailable(
    hass, mock_client, config_entry, number_entry
) -> None:
    """Make the percentage unavailable while the Shelly RPC link is disconnected."""
    mock_client.connected = False

    config_entry.runtime_data.coordinator._async_handle_connection_change()
    await hass.async_block_till_done()

    assert hass.states.get(number_entry.entity_id).state == "unavailable"


@pytest.mark.parametrize("brightness", [-1, 101])
async def test_out_of_range_service_value_is_rejected(
    hass, mock_client, number_entry, brightness: float
) -> None:
    """Reject service values outside the advertised percentage range."""
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {"entity_id": number_entry.entity_id, "value": brightness},
            blocking=True,
        )

    mock_client.async_set_night_mode_brightness.assert_not_awaited()
    assert float(hass.states.get(number_entry.entity_id).state) == 25


@pytest.mark.parametrize(
    "error",
    [
        DeviceConnectionError("Disconnected"),
        InvalidAuthError("Invalid credentials"),
        RpcCallError(500, "Update failed"),
        ShellyUnsupportedDeviceError("Invalid config"),
        ValueError("Invalid brightness"),
    ],
)
async def test_device_error_is_reported_without_changing_brightness(
    hass, mock_client, number_entry, error: Exception
) -> None:
    """Report failed writes as Home Assistant errors without optimistic updates."""
    mock_client.async_set_night_mode_brightness.side_effect = error

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {"entity_id": number_entry.entity_id, "value": 50},
            blocking=True,
        )

    assert float(hass.states.get(number_entry.entity_id).state) == 25
    assert mock_client.async_get_led_config.await_count == 1


async def test_unload_stops_brightness_entity(
    hass, mock_client, config_entry, number_entry
) -> None:
    """Unload the number, retain its unavailable registry state, and close RPC."""
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(number_entry.entity_id)
    assert state.state == "unavailable"
    assert state.attributes["restored"] is True
    mock_client.async_disconnect.assert_awaited_once()
