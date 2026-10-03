"""Tests for the status LED light entity and its device association."""

from datetime import time
from unittest.mock import patch

import pytest
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.light import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.components.time import DOMAIN as TIME_DOMAIN
from homeassistant.components.time.const import SERVICE_SET_VALUE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_TIME, CONF_HOST, EntityCategory
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shelly_led_control.api import night_mode_from_config
from custom_components.shelly_led_control.const import DOMAIN
from custom_components.shelly_led_control.coordinator import ShellyLedState

TEST_MAC = "aa:bb:cc:dd:ee:ff"

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def _setup_entry(hass, mock_client, unique_id: str = TEST_MAC) -> MockConfigEntry:
    """Set up an entry backed by a mocked connected Shelly client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Waschmaschine",
        unique_id=unique_id,
        data={CONF_HOST: "192.0.2.10"},
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.shelly_led_control.ShellyLedClient",
        return_value=mock_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    return entry


def _registry_entry(hass, entry: MockConfigEntry):
    """Return the status LED registry entry, excluding relay-state presets."""
    return next(
        registry_entry
        for registry_entry in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if registry_entry.domain == LIGHT_DOMAIN
        and registry_entry.translation_key == "status_led"
    )


def _registry_entries(hass, entry: MockConfigEntry):
    """Return every entity-registry entry created for a config entry."""
    return er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)


@pytest.mark.asyncio
async def test_entity_state_and_turn_off_call(hass, mock_client) -> None:
    """Expose LED mode as a light and map turn-off to the Shelly client."""
    entry = await _setup_entry(hass, mock_client)
    registry_entry = _registry_entry(hass, entry)

    assert hass.states.get(registry_entry.entity_id).state == "on"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": registry_entry.entity_id},
        blocking=True,
    )

    mock_client.async_set_led_enabled.assert_awaited_once_with(False)


@pytest.mark.asyncio
async def test_night_mode_switch_and_time_window(hass, mock_client) -> None:
    """Expose and update the night-mode switch, start time, and end time."""
    entry = await _setup_entry(hass, mock_client)
    entries = _registry_entries(hass, entry)
    switch_entry = next(item for item in entries if item.domain == "switch")
    start_entry = next(
        item for item in entries if item.unique_id.endswith("night_mode_start")
    )
    end_entry = next(
        item for item in entries if item.unique_id.endswith("night_mode_end")
    )

    assert hass.states.get(switch_entry.entity_id).state == "on"
    assert hass.states.get(start_entry.entity_id).state == "22:00:00"
    assert hass.states.get(end_entry.entity_id).state == "06:00:00"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": switch_entry.entity_id}, blocking=True
    )
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": start_entry.entity_id, ATTR_TIME: "21:30"},
        blocking=True,
    )

    mock_client.async_set_night_mode_enabled.assert_awaited_once_with(False)
    mock_client.async_set_night_mode_start.assert_awaited_once_with(time(21, 30))


@pytest.mark.asyncio
async def test_entity_uses_configuration_category(hass, mock_client) -> None:
    """Place the status LED in Home Assistant's configuration category."""
    entry = await _setup_entry(hass, mock_client)

    assert _registry_entry(hass, entry).entity_category is EntityCategory.CONFIG


@pytest.mark.asyncio
async def test_off_mode_and_turn_on_call(hass, mock_client) -> None:
    """Map an off LED mode to an off light and forward turn-on."""
    mock_client.async_get_led_config.side_effect = None
    mock_client.async_get_led_config.return_value = {
        "leds": {
            "mode": "off",
            "night_mode": {
                "enable": False,
                "active_between": ["22:00", "06:00"],
            },
        }
    }
    entry = await _setup_entry(hass, mock_client)
    registry_entry = _registry_entry(hass, entry)

    assert hass.states.get(registry_entry.entity_id).state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": registry_entry.entity_id},
        blocking=True,
    )

    mock_client.async_set_led_enabled.assert_awaited_once_with(True)


@pytest.mark.asyncio
async def test_night_mode_turns_entity_off_inside_zero_brightness_window(
    hass, mock_client
) -> None:
    """Expose the physical LED as off while zero-brightness night mode is active."""
    mock_client.async_get_led_config.side_effect = None
    mock_client.async_get_led_config.return_value = {
        "leds": {
            "mode": "power",
            "night_mode": {
                "enable": True,
                "brightness": 0,
                "active_between": ["20:00", "08:00"],
            },
        }
    }
    mock_client.async_get_device_time.return_value = time(20, 0)

    entry = await _setup_entry(hass, mock_client)
    registry_entry = _registry_entry(hass, entry)

    assert hass.states.get(registry_entry.entity_id).state == "off"


def test_zero_brightness_night_mode_turns_light_off_inside_window() -> None:
    """Report the LED as off while a zero-brightness night mode is active."""
    night_mode = night_mode_from_config(
        {
            "leds": {
                "night_mode": {
                    "enable": True,
                    "brightness": 0,
                    "active_between": ["22:00", "06:00"],
                }
            }
        }
    )
    active_state = ShellyLedState(
        mode="power",
        night_mode=night_mode,
        device_time=time(22, 0),
    )
    inactive_state = ShellyLedState(
        mode="power", night_mode=night_mode, device_time=time(6, 0)
    )

    assert not active_state.is_on
    assert inactive_state.is_on


@pytest.mark.parametrize(
    ("normal_brightness", "enabled", "clock", "expected_on"),
    [
        (0, False, None, False),
        (0, True, time(12, 0), False),
        (0, True, time(23, 0), True),
        (0, True, None, True),
        (None, False, None, True),
    ],
)
def test_normal_zero_brightness_respects_night_mode_and_unknown_clock(
    led_config: dict,
    normal_brightness: float | None,
    enabled: bool,
    clock: time | None,
    expected_on: bool,
) -> None:
    """Use normal zero only outside night mode and retain unknown LED states."""
    led_config["leds"]["night_mode"]["enable"] = enabled
    state = ShellyLedState(
        mode="power",
        night_mode=night_mode_from_config(led_config),
        device_time=clock,
        normal_brightness=normal_brightness,
    )

    assert state.is_on is expected_on


@pytest.mark.asyncio
async def test_connection_loss_marks_entity_unavailable(hass, mock_client) -> None:
    """Mark the light unavailable when its RPC connection is lost."""
    entry = await _setup_entry(hass, mock_client)
    registry_entry = _registry_entry(hass, entry)
    mock_client.connected = False

    entry.runtime_data.coordinator._async_handle_connection_change()
    await hass.async_block_till_done()

    assert hass.states.get(registry_entry.entity_id).state == "unavailable"


@pytest.mark.asyncio
async def test_device_is_owned_by_this_config_entry(hass, mock_client) -> None:
    """Associate the status LED with its own integration-owned device entry."""
    entry = await _setup_entry(hass, mock_client)
    registry_entry = _registry_entry(hass, entry)
    device = dr.async_get(hass).async_get(registry_entry.device_id)

    assert device.config_entries == {entry.entry_id}
    assert device.identifiers == {(DOMAIN, TEST_MAC)}
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, TEST_MAC)}


@pytest.mark.asyncio
async def test_multiple_shellys_have_distinct_entity_unique_ids(
    hass, mock_client
) -> None:
    """Give each configured Shelly a stable entity unique ID based on its MAC."""
    second_mac = "11:22:33:44:55:66"
    first_entry = await _setup_entry(hass, mock_client)
    second_entry = await _setup_entry(hass, mock_client, unique_id=second_mac)
    unique_ids = {
        _registry_entry(hass, first_entry).unique_id,
        _registry_entry(hass, second_entry).unique_id,
    }

    assert unique_ids == {f"{TEST_MAC}_status_led", f"{second_mac}_status_led"}
