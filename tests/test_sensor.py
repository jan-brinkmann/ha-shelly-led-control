"""Tests for effective status LED brightness and Home Assistant recording."""

from datetime import time, timedelta
from unittest.mock import patch

import pytest
from homeassistant.components.recorder import history
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import CONF_HOST, PERCENTAGE
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.shelly_led_control.const import DOMAIN

TEST_MAC = "aa:bb:cc:dd:ee:ff"

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture
def mock_recorder_before_hass(recorder_db_url: str) -> None:
    """Prepare Recorder's database fixture before Home Assistant starts."""


async def _setup_entry(hass, mock_client) -> MockConfigEntry:
    """Load the integration and its read-only sensors using mocked device data."""
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


def _sensor_entry(hass, entry: MockConfigEntry) -> er.RegistryEntry:
    """Return the numeric brightness sensor registered for the device."""
    return next(
        item
        for item in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if item.domain == SENSOR_DOMAIN
    )


@pytest.mark.parametrize(
    ("language", "name"),
    [("de", "Dimmwert Status-LED"), ("en", "Status LED brightness")],
)
async def test_brightness_sensor_metadata(
    hass, mock_client, language: str, name: str
) -> None:
    """Expose a default-enabled percentage sensor eligible for statistics."""
    hass.config.language = language
    entry = await _setup_entry(hass, mock_client)
    sensor = _sensor_entry(hass, entry)
    state = hass.states.get(sensor.entity_id)

    assert sensor.original_name == name
    assert sensor.unique_id == f"{TEST_MAC}_status_led_brightness"
    assert sensor.entity_category is None
    assert sensor.disabled_by is None
    assert state.attributes["unit_of_measurement"] == PERCENTAGE
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert "device_class" not in state.attributes
    device = dr.async_get(hass).async_get(sensor.device_id)
    assert device.config_entries == {entry.entry_id}
    assert device.identifiers == {(DOMAIN, TEST_MAC)}
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, TEST_MAC)}
    assert not hass.services.has_service(SENSOR_DOMAIN, "set_value")


@pytest.mark.parametrize(
    ("mode", "output", "clock", "enabled", "night_brightness", "expected"),
    [
        ("power", None, time(12, 0), True, 25, "100"),
        ("power", None, time(23, 0), True, 25, "25"),
        ("power", None, time(23, 0), True, 0, "0"),
        ("power", None, time(23, 0), True, 100, "100"),
        ("power", None, time(23, 0), False, 25, "100"),
        ("power", None, None, True, 25, "unknown"),
        ("power", None, None, False, 25, "100"),
        ("power", None, time(23, 0), True, None, "unknown"),
        ("switch", True, time(12, 0), True, 25, "80"),
        ("switch", False, time(12, 0), True, 25, "40"),
        ("switch", None, time(12, 0), True, 25, "unknown"),
        ("switch", False, time(23, 0), True, 25, "25"),
        ("switch", None, time(23, 0), True, 25, "25"),
        ("off", None, time(12, 0), True, 25, "0"),
        ("off", None, time(23, 0), True, 25, "0"),
        ("off", None, None, True, 25, "0"),
        ("unsupported", None, time(23, 0), True, 25, "unknown"),
    ],
)
async def test_brightness_uses_current_mode_and_night_schedule(
    hass,
    mock_client,
    led_config,
    mode: str,
    output: bool | None,
    clock: time | None,
    enabled: bool,
    night_brightness: float | None,
    expected: str,
) -> None:
    """Select normal, night or zero brightness without guessing unknown values."""
    led_config["leds"]["mode"] = mode
    led_config["leds"]["night_mode"].update(enable=enabled, brightness=night_brightness)
    mock_client.async_get_device_time.return_value = clock
    mock_client.async_get_switch_output.return_value = output
    entry = await _setup_entry(hass, mock_client)
    sensor = _sensor_entry(hass, entry)

    assert hass.states.get(sensor.entity_id).state == expected
    if mode == "switch":
        mock_client.async_get_switch_output.assert_awaited_once()
    else:
        mock_client.async_get_switch_output.assert_not_awaited()
    mock_client.async_set_led_enabled.assert_not_awaited()
    mock_client.async_set_night_mode_brightness.assert_not_awaited()


async def test_night_brightness_overrides_lower_normal_brightness(
    hass, mock_client, led_config
) -> None:
    """Use the night brightness directly, including values above normal brightness."""
    led_config["leds"]["colors"]["power"]["brightness"] = 10
    led_config["leds"]["night_mode"]["brightness"] = 75.5
    mock_client.async_get_device_time.return_value = time(23, 0)
    entry = await _setup_entry(hass, mock_client)
    sensor = _sensor_entry(hass, entry)

    assert hass.states.get(sensor.entity_id).state == "75.5"


async def test_missing_normal_brightness_keeps_other_entities_available(
    hass, mock_client, led_config
) -> None:
    """Keep existing platforms working when optional normal brightness is absent."""
    del led_config["leds"]["colors"]
    entry = await _setup_entry(hass, mock_client)
    sensor = _sensor_entry(hass, entry)

    assert hass.states.get(sensor.entity_id).state == "unknown"
    for item in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id):
        assert hass.states.get(item.entity_id).state != "unavailable"


@pytest.mark.parametrize("night_brightness", [0, 25, 100])
@pytest.mark.parametrize(
    ("before", "boundary", "entering"),
    [
        (time(21, 59, 40), time(22, 0), True),
        (time(5, 59, 40), time(6, 0), False),
    ],
)
async def test_brightness_refreshes_at_night_boundaries(
    hass,
    mock_client,
    led_config,
    night_brightness: float,
    before: time,
    boundary: time,
    entering: bool,
) -> None:
    """Update at both window boundaries without waiting for the fallback poll."""
    led_config["leds"]["night_mode"]["brightness"] = night_brightness
    mock_client.async_get_device_time.return_value = before
    entry = await _setup_entry(hass, mock_client)
    sensor = _sensor_entry(hass, entry)
    initial = 100 if entering else night_brightness
    assert float(hass.states.get(sensor.entity_id).state) == initial

    mock_client.async_get_device_time.return_value = boundary
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=20))
    await hass.async_block_till_done()

    expected = night_brightness if entering else 100
    assert float(hass.states.get(sensor.entity_id).state) == expected
    assert mock_client.async_get_led_config.await_count == 2


async def test_brightness_only_config_change_updates_sensor(
    hass, mock_client, led_config
) -> None:
    """Notify entities when only brightness changes at the same mode and time."""
    entry = await _setup_entry(hass, mock_client)
    sensor = _sensor_entry(hass, entry)
    led_config["leds"]["colors"]["power"]["brightness"] = 42.5

    await entry.runtime_data.coordinator.async_request_refresh()

    assert hass.states.get(sensor.entity_id).state == "42.5"


async def test_relay_change_updates_switch_mode_brightness(
    hass, mock_client, led_config
) -> None:
    """Refresh the brightness after a relay push while other LED settings match."""
    led_config["leds"]["mode"] = "switch"
    entry = await _setup_entry(hass, mock_client)
    sensor = _sensor_entry(hass, entry)
    assert hass.states.get(sensor.entity_id).state == "80"
    mock_client.async_get_switch_output.return_value = False
    refresh, _ = mock_client.async_set_callbacks.call_args.args

    await refresh()

    assert hass.states.get(sensor.entity_id).state == "40"


async def test_brightness_disconnect_recovery_and_unload(hass, mock_client) -> None:
    """Restore unchanged brightness on reconnect and remove it when unloaded."""
    entry = await _setup_entry(hass, mock_client)
    sensor = _sensor_entry(hass, entry)
    _, unavailable = mock_client.async_set_callbacks.call_args.args
    mock_client.connected = False
    unavailable()
    assert hass.states.get(sensor.entity_id).state == "unavailable"

    mock_client.connected = True
    await entry.runtime_data.coordinator.async_request_refresh()
    assert hass.states.get(sensor.entity_id).state == "100"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(sensor.entity_id).state == "unavailable"


async def test_brightness_is_recorded_in_history(
    recorder_mock, hass, mock_client, led_config
) -> None:
    """Record brightness transitions through HA Recorder without custom storage."""
    start = dt_util.utcnow() - timedelta(seconds=1)
    entry = await _setup_entry(hass, mock_client)
    sensor = _sensor_entry(hass, entry)
    await async_wait_recording_done(hass)
    led_config["leds"]["colors"]["power"]["brightness"] = 42.5
    await entry.runtime_data.coordinator.async_request_refresh()
    await async_wait_recording_done(hass)

    states = await hass.async_add_executor_job(
        history.get_significant_states,
        hass,
        start,
        dt_util.utcnow() + timedelta(seconds=1),
        [sensor.entity_id],
    )

    assert [state.state for state in states[sensor.entity_id]] == ["100", "42.5"]
