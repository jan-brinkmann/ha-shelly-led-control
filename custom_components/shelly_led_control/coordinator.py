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
    led_mode_from_config,
    night_mode_from_config,
)
from .const import DOMAIN, LED_MODE_OFF, UPDATE_INTERVAL

if TYPE_CHECKING:
    from . import ShellyLedConfigEntry


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ShellyLedState:
    """Represent the effective LED indication from PLUGS_UI configuration."""

    mode: str
    night_mode: ShellyNightMode
    device_time: time | None

    @property
    def is_on(self) -> bool:
        """Return whether the physical LED is on at the Shelly's current time."""
        return self.mode != LED_MODE_OFF and not (
            self.device_time is not None
            and self.night_mode.hides_led_at(self.device_time)
        )


class ShellyLedCoordinator(DataUpdateCoordinator[ShellyLedState]):
    """Coordinate PLUGS_UI configuration and availability for one Shelly."""

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
        """Fetch LED configuration and its Shelly-local time for state mapping.

        Raises:
            ConfigEntryAuthFailed: If stored Shelly credentials are no longer valid.
            UpdateFailed: If the device cannot be contacted or returns bad data.
        """
        try:
            config = await self.client.async_get_led_config()
            device_time = await self.client.async_get_device_time()
            state = ShellyLedState(
                mode=led_mode_from_config(config),
                night_mode=night_mode_from_config(config),
                device_time=device_time,
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
        """Notify entities immediately when the persistent RPC link disconnects."""
        self.async_update_listeners()

    def async_cancel_scheduled_updates(self) -> None:
        """Cancel the timer that updates entities at a night-mode boundary."""
        if self._cancel_night_mode_transition is not None:
            self._cancel_night_mode_transition()
            self._cancel_night_mode_transition = None

    @callback
    def _async_schedule_night_mode_transition(
        self, night_mode: ShellyNightMode, device_time: time | None
    ) -> None:
        """Refresh entities at a zero-brightness night-mode boundary."""
        self.async_cancel_scheduled_updates()
        if (
            not night_mode.enabled
            or night_mode.brightness != 0
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
