"""State coordination for Shelly LED Control."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import TYPE_CHECKING

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    ShellyLedClient,
    ShellyNightMode,
    ShellyUnsupportedDeviceError,
    led_brightness_from_config,
    led_mode_from_config,
    night_mode_from_config,
)
from .const import DOMAIN, LED_MODE_OFF, UPDATE_INTERVAL

if TYPE_CHECKING:
    from . import ShellyLedConfigEntry


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ShellyLedState:
    """Represent LED indication, effective brightness and night-mode activity."""

    mode: str
    night_mode: ShellyNightMode
    device_time: time | None
    normal_brightness: float | None = None

    @property
    def brightness(self) -> float | None:
        """Return effective brightness in percent, or None if it is unknown.

        Disabled indication is always zero. Active night mode overrides normal
        brightness. An enabled schedule without a synchronized clock is unknown.
        """
        if self.mode == LED_MODE_OFF:
            return 0
        if self.mode not in {"power", "switch"}:
            return None
        if (active := self.night_mode_active) is None:
            return None
        if active:
            return self.night_mode.brightness
        return self.normal_brightness

    @property
    def night_mode_active(self) -> bool | None:
        """Return current night-mode activity, or None if the clock is unknown.

        Disabled night mode is always inactive, even before clock synchronization.
        """
        if not self.night_mode.enabled:
            return False
        if self.device_time is None:
            return None
        return self.night_mode.is_active_at(self.device_time)

    @property
    def is_on(self) -> bool:
        """Return whether indication is enabled and its brightness is not zero.

        Unknown brightness retains the enabled indication state. Normal zero
        brightness suppresses the LED only when night mode is known to be inactive.
        """
        return self.mode != LED_MODE_OFF and not (
            (
                self.device_time is not None
                and self.night_mode.hides_led_at(self.device_time)
            )
            or (self.night_mode_active is False and self.normal_brightness == 0)
        )


class ShellyLedCoordinator(DataUpdateCoordinator[ShellyLedState]):
    """Coordinate LED configuration, relay state and availability for one Shelly."""

    config_entry: ShellyLedConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ShellyLedConfigEntry,
        client: ShellyLedClient,
    ) -> None:
        """Initialize coordinator callbacks and a conservative fallback poll."""
        self.client = client
        self._cancel_night_mode_transition: CALLBACK_TYPE | None = None
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        client.async_set_callbacks(
            self.async_request_refresh, self._async_handle_connection_change
        )

    async def _async_update_data(self) -> ShellyLedState:
        """Fetch configuration, Shelly-local time and switch-mode relay output.

        Raises:
            ConfigEntryAuthFailed: If stored Shelly credentials are no longer valid.
            UpdateFailed: If the device cannot be contacted or returns bad data.
        """
        try:
            config = await self.client.async_get_led_config()
            device_time = await self.client.async_get_device_time()
            mode = led_mode_from_config(config)
            switch_output = (
                await self.client.async_get_switch_output()
                if mode == "switch"
                else None
            )
            state = ShellyLedState(
                mode=mode,
                night_mode=night_mode_from_config(config),
                device_time=device_time,
                normal_brightness=led_brightness_from_config(config, switch_output),
            )
            self._async_schedule_night_mode_transition(state.night_mode, device_time)
            return state
        except InvalidAuthError as err:
            raise ConfigEntryAuthFailed("Invalid Shelly credentials") from err
        except (
            DeviceConnectionError,
            RpcCallError,
            ShellyUnsupportedDeviceError,
        ) as err:
            raise UpdateFailed("Unable to update Shelly LED configuration") from err

    async def async_set_enabled(self, enabled: bool) -> None:
        """Apply a requested LED indication state and refresh the coordinator.

        Raises:
            HomeAssistantError: If the Shelly cannot accept the requested change.
        """
        try:
            await self.client.async_set_led_enabled(enabled)
            await self.async_request_refresh()
        except InvalidAuthError as err:
            raise HomeAssistantError("Shelly credentials are no longer valid") from err
        except (
            DeviceConnectionError,
            RpcCallError,
            ShellyUnsupportedDeviceError,
        ) as err:
            raise HomeAssistantError(
                "Unable to update Shelly LED configuration"
            ) from err

    async def async_set_brightness(self, value: float) -> None:
        """Apply normal LED brightness and refresh entities from the device.

        Args:
            value: The LED brightness in percent, from 0 to 100 inclusive.

        Raises:
            HomeAssistantError: If the value is invalid or the device update fails.
        """
        try:
            await self.client.async_set_led_brightness(value)
            await self.async_request_refresh()
        except InvalidAuthError as err:
            raise HomeAssistantError("Shelly credentials are no longer valid") from err
        except (
            DeviceConnectionError,
            RpcCallError,
            ShellyUnsupportedDeviceError,
            ValueError,
        ) as err:
            raise HomeAssistantError("Unable to update Shelly LED brightness") from err

    async def async_set_night_mode_enabled(self, enabled: bool) -> None:
        """Apply a requested night-mode enabled state and refresh entities.

        Raises:
            HomeAssistantError: If the Shelly cannot accept the requested change.
        """
        try:
            await self.client.async_set_night_mode_enabled(enabled)
            await self.async_request_refresh()
        except InvalidAuthError as err:
            raise HomeAssistantError("Shelly credentials are no longer valid") from err
        except (
            DeviceConnectionError,
            RpcCallError,
            ShellyUnsupportedDeviceError,
            ValueError,
        ) as err:
            raise HomeAssistantError("Unable to update Shelly night mode") from err

    async def async_set_night_mode_brightness(self, value: float) -> None:
        """Apply night-mode brightness and refresh all entities from the device.

        Args:
            value: The LED brightness in percent, from 0 to 100 inclusive.

        Raises:
            HomeAssistantError: If the Shelly cannot accept the requested change.
        """
        try:
            await self.client.async_set_night_mode_brightness(value)
            await self.async_request_refresh()
        except InvalidAuthError as err:
            raise HomeAssistantError("Shelly credentials are no longer valid") from err
        except (
            DeviceConnectionError,
            RpcCallError,
            ShellyUnsupportedDeviceError,
            ValueError,
        ) as err:
            raise HomeAssistantError("Unable to update Shelly night mode") from err

    async def async_set_night_mode_start(self, value: time) -> None:
        """Apply a requested night-mode start time and refresh entities.

        Args:
            value: The whole-minute local time supplied by Home Assistant.

        Raises:
            HomeAssistantError: If the Shelly cannot accept the requested change.
        """
        try:
            await self.client.async_set_night_mode_start(value)
            await self.async_request_refresh()
        except InvalidAuthError as err:
            raise HomeAssistantError("Shelly credentials are no longer valid") from err
        except (
            DeviceConnectionError,
            RpcCallError,
            ShellyUnsupportedDeviceError,
            ValueError,
        ) as err:
            raise HomeAssistantError("Unable to update Shelly night mode") from err

    async def async_set_night_mode_end(self, value: time) -> None:
        """Apply a requested night-mode end time and refresh entities.

        Args:
            value: The whole-minute local time supplied by Home Assistant.

        Raises:
            HomeAssistantError: If the Shelly cannot accept the requested change.
        """
        try:
            await self.client.async_set_night_mode_end(value)
            await self.async_request_refresh()
        except InvalidAuthError as err:
            raise HomeAssistantError("Shelly credentials are no longer valid") from err
        except (
            DeviceConnectionError,
            RpcCallError,
            ShellyUnsupportedDeviceError,
            ValueError,
        ) as err:
            raise HomeAssistantError("Unable to update Shelly night mode") from err

    @callback
    def _async_handle_connection_change(self) -> None:
        """Mark data unavailable on disconnect and recover on the next refresh."""
        self.async_set_update_error(
            UpdateFailed("Shelly RPC connection is unavailable")
        )

    def async_cancel_scheduled_updates(self) -> None:
        """Cancel the timer that updates entities at a night-mode boundary."""
        if self._cancel_night_mode_transition is not None:
            self._cancel_night_mode_transition()
            self._cancel_night_mode_transition = None

    @callback
    def _async_schedule_night_mode_transition(
        self, night_mode: ShellyNightMode, device_time: time | None
    ) -> None:
        """Refresh LED, brightness and activity at each enabled night-mode boundary."""
        self.async_cancel_scheduled_updates()
        if (
            not night_mode.enabled
            or device_time is None
            or night_mode.start == night_mode.end
        ):
            return

        transition = dt_util.now() + self._time_until_next_night_mode_transition(
            night_mode, device_time
        )
        self._cancel_night_mode_transition = async_track_point_in_time(
            self.hass, self._async_handle_night_mode_transition, transition
        )

    @staticmethod
    def _time_until_next_night_mode_transition(
        night_mode: ShellyNightMode, device_time: time
    ) -> timedelta:
        """Return the duration until the Shelly reaches its next time boundary."""
        current_seconds = (
            device_time.hour * 3600 + device_time.minute * 60 + device_time.second
        )
        seconds_until = []
        for boundary in (night_mode.start, night_mode.end):
            boundary_seconds = (
                boundary.hour * 3600 + boundary.minute * 60 + boundary.second
            )
            duration = boundary_seconds - current_seconds
            if duration <= 0:
                duration += 24 * 60 * 60
            seconds_until.append(duration)
        return timedelta(seconds=min(seconds_until))

    @callback
    def _async_handle_night_mode_transition(self, now: datetime) -> None:
        """Refresh the state against the Shelly clock after a time boundary."""
        del now
        self._cancel_night_mode_transition = None
        self.hass.async_create_task(
            self.async_request_refresh(), "refresh Shelly LED night-mode state"
        )
