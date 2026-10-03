"""Tests for distinguishing enabled night mode from current night-mode activity."""

from datetime import time, timedelta
from unittest.mock import patch

import pytest
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.time import DOMAIN as TIME_DOMAIN
from homeassistant.components.time.const import SERVICE_SET_VALUE
from homeassistant.const import ATTR_TIME, CONF_HOST, EntityCategory
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.shelly_led_control.const import DOMAIN

TEST_MAC = "aa:bb:cc:dd:ee:ff"

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def _setup_entry(hass, mock_client) -> MockConfigEntry:
    """Load all LED platforms using a mocked connected Shelly device."""
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


def _registry_entry(hass, entry: MockConfigEntry, domain: str) -> er.RegistryEntry:
    """Return the entity registered under the requested platform domain."""
    return next(
        item
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if item.domain == domain
    )


@pytest.mark.parametrize(
    ("language", "switch_name", "sensor_name"),
    [
        ("de", "Nachtmodus nutzen", "Nachtmodus aktiv"),
        ("en", "Use night mode", "Night mode active"),
    ],
)
async def test_activity_sensor_and_switch_names(
    hass, mock_client, language: str, switch_name: str, sensor_name: str
) -> None:
    """Expose translated enable and activity names with stable device identity."""
    hass.config.language = language
    entry = await _setup_entry(hass, mock_client)
    sensor = _registry_entry(hass, entry, BINARY_SENSOR_DOMAIN)
    switch = _registry_entry(hass, entry, "switch")

    assert sensor.original_name == sensor_name
    assert switch.original_name == switch_name
    assert sensor.unique_id == f"{TEST_MAC}_night_mode_active"
    assert switch.unique_id == f"{TEST_MAC}_night_mode"
    assert sensor.entity_category is None
    assert switch.entity_category is EntityCategory.CONFIG
    assert sensor.device_id == switch.device_id
    device = dr.async_get(hass).async_get(sensor.device_id)
    assert device.config_entries == {entry.entry_id}
    assert device.identifiers == {(DOMAIN, TEST_MAC)}
    assert not hass.services.has_service(BINARY_SENSOR_DOMAIN, "turn_on")
    assert not hass.services.has_service(BINARY_SENSOR_DOMAIN, "turn_off")


async def test_existing_switch_entity_id_survives_rename(hass, mock_client) -> None:
    """Keep the existing switch registry entry when its translated name changes."""
    previous = er.async_get(hass).async_get_or_create(
        "switch",
        DOMAIN,
        f"{TEST_MAC}_night_mode",
        suggested_object_id="waschmaschine_night_mode",
        original_name="Night mode",
    )
    entry = await _setup_entry(hass, mock_client)
    switch = _registry_entry(hass, entry, "switch")

    assert switch.entity_id == previous.entity_id
    assert switch.original_name == "Use night mode"


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("brightness", [0, 25])
@pytest.mark.parametrize(
    ("window", "device_time", "inside"),
    [
        (["22:00", "06:00"], time(21, 59, 59), False),
        (["22:00", "06:00"], time(22, 0), True),
        (["22:00", "06:00"], time(0, 0), True),
        (["22:00", "06:00"], time(5, 59, 59), True),
        (["22:00", "06:00"], time(6, 0), False),
        (["09:00", "17:00"], time(8, 59, 59), False),
        (["09:00", "17:00"], time(9, 0), True),
        (["09:00", "17:00"], time(16, 59, 59), True),
        (["09:00", "17:00"], time(17, 0), False),
        (["10:00", "10:00"], time(0, 0), True),
        (["10:00", "10:00"], time(12, 0), True),
    ],
)
async def test_activity_uses_enabled_state_and_shelly_local_time(
    hass,
    mock_client,
    led_config,
    enabled: bool,
    brightness: float,
    window: list[str],
    device_time: time,
    inside: bool,
) -> None:
    """Report activity from the enabled flag and time window at any brightness."""
    led_config["leds"]["night_mode"].update(
        enable=enabled, brightness=brightness, active_between=window
    )
    mock_client.async_get_device_time.return_value = device_time
    entry = await _setup_entry(hass, mock_client)
    sensor = _registry_entry(hass, entry, BINARY_SENSOR_DOMAIN)
    switch = _registry_entry(hass, entry, "switch")

    assert hass.states.get(sensor.entity_id).state == (
        "on" if enabled and inside else "off"
    )
    assert hass.states.get(switch.entity_id).state == ("on" if enabled else "off")


async def test_activity_is_independent_of_led_mode(
    hass, mock_client, led_config
) -> None:
    """Keep night mode active inside its window even if LED indication is off."""
    led_config["leds"]["mode"] = "off"
    mock_client.async_get_device_time.return_value = time(23, 0)
    entry = await _setup_entry(hass, mock_client)

    sensor = _registry_entry(hass, entry, BINARY_SENSOR_DOMAIN)
    light = _registry_entry(hass, entry, "light")
    assert hass.states.get(sensor.entity_id).state == "on"
    assert hass.states.get(light.entity_id).state == "off"


@pytest.mark.parametrize(("enabled", "expected"), [(True, "unknown"), (False, "off")])
async def test_unsynchronized_clock_does_not_invent_activity(
    hass, mock_client, led_config, enabled: bool, expected: str
) -> None:
    """Report unknown activity without a clock unless night mode is disabled."""
    led_config["leds"]["night_mode"]["enable"] = enabled
    mock_client.async_get_device_time.return_value = None
    entry = await _setup_entry(hass, mock_client)
    sensor = _registry_entry(hass, entry, BINARY_SENSOR_DOMAIN)

    assert hass.states.get(sensor.entity_id).state == expected


@pytest.mark.parametrize("brightness", [0, 25])
@pytest.mark.parametrize(
    ("before", "boundary", "initial_state", "expected_state"),
    [
        (time(21, 59, 40), time(22, 0), "off", "on"),
        (time(5, 59, 40), time(6, 0), "on", "off"),
    ],
)
async def test_activity_refreshes_at_boundary_without_waiting_for_poll(
    hass,
    mock_client,
    led_config,
    brightness: float,
    before: time,
    boundary: time,
    initial_state: str,
    expected_state: str,
) -> None:
    """Refresh at both boundaries within seconds, including nonzero brightness."""
    led_config["leds"]["night_mode"]["brightness"] = brightness
    mock_client.async_get_device_time.return_value = before
    entry = await _setup_entry(hass, mock_client)
    sensor = _registry_entry(hass, entry, BINARY_SENSOR_DOMAIN)
    assert hass.states.get(sensor.entity_id).state == initial_state

    mock_client.async_get_device_time.return_value = boundary
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    assert hass.states.get(sensor.entity_id).state == expected_state
    assert mock_client.async_get_led_config.await_count == 2


async def test_using_night_mode_updates_activity_immediately(
    hass, mock_client, led_config
) -> None:
    """Update activity when use is toggled, and cancel a disabled mode's timer."""
    mock_client.async_get_device_time.return_value = time(5, 59, 40)

    async def set_enabled(enabled: bool) -> None:
        """Apply the mock enable flag so the next refresh reads the changed state."""
        led_config["leds"]["night_mode"]["enable"] = enabled

    mock_client.async_set_night_mode_enabled.side_effect = set_enabled
    entry = await _setup_entry(hass, mock_client)
    sensor = _registry_entry(hass, entry, BINARY_SENSOR_DOMAIN)
    switch = _registry_entry(hass, entry, "switch")
    assert hass.states.get(sensor.entity_id).state == "on"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": switch.entity_id}, blocking=True
    )
    assert hass.states.get(sensor.entity_id).state == "off"
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()
    assert mock_client.async_get_led_config.await_count == 2

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": switch.entity_id}, blocking=True
    )
    assert hass.states.get(sensor.entity_id).state == "on"


async def test_changing_time_window_updates_activity(
    hass, mock_client, led_config
) -> None:
    """Recompute activity on the requested refresh after either boundary changes."""

    async def set_start(value: time) -> None:
        """Update the start time returned by the mock device."""
        led_config["leds"]["night_mode"]["active_between"][0] = value.strftime("%H:%M")

    async def set_end(value: time) -> None:
        """Update the end time returned by the mock device."""
        led_config["leds"]["night_mode"]["active_between"][1] = value.strftime("%H:%M")

    mock_client.async_set_night_mode_start.side_effect = set_start
    mock_client.async_set_night_mode_end.side_effect = set_end
    entry = await _setup_entry(hass, mock_client)
    sensor = _registry_entry(hass, entry, BINARY_SENSOR_DOMAIN)
    times = {
        item.translation_key: item.entity_id
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if item.domain == TIME_DOMAIN
    }
    assert hass.states.get(sensor.entity_id).state == "off"

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": times["night_mode_start"], ATTR_TIME: "10:00"},
        blocking=True,
    )
    assert hass.states.get(sensor.entity_id).state == "on"
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": times["night_mode_end"], ATTR_TIME: "11:00"},
        blocking=True,
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=15))
    await hass.async_block_till_done()
    assert hass.states.get(sensor.entity_id).state == "off"


async def test_connection_loss_makes_activity_unavailable(hass, mock_client) -> None:
    """Mark activity unavailable on disconnect and recover it after reconnection."""
    entry = await _setup_entry(hass, mock_client)
    sensor = _registry_entry(hass, entry, BINARY_SENSOR_DOMAIN)
    mock_client.connected = False
    entry.runtime_data.coordinator._async_handle_connection_change()
    await hass.async_block_till_done()
    assert hass.states.get(sensor.entity_id).state == "unavailable"

    mock_client.connected = True
    await entry.runtime_data.coordinator.async_request_refresh()
    assert hass.states.get(sensor.entity_id).state == "off"


async def test_unload_cancels_activity_boundary_updates(hass, mock_client) -> None:
    """Stop the sensor and boundary refresh timer when the entry is unloaded."""
    mock_client.async_get_device_time.return_value = time(21, 59, 40)
    entry = await _setup_entry(hass, mock_client)
    sensor = _registry_entry(hass, entry, BINARY_SENSOR_DOMAIN)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    assert hass.states.get(sensor.entity_id).state == "unavailable"
    assert mock_client.async_get_led_config.await_count == 1
    mock_client.async_disconnect.assert_awaited_once()
