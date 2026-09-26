"""State coordination for Shelly LED Control."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import time
from typing import TYPE_CHECKING

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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
    """Represent the LED indication state derived from PLUGS_UI configuration."""

    mode: str
    night_mode: ShellyNightMode

    @property
    def is_on(self) -> bool:
        """Return whether the Shelly LED indication is enabled."""
        return self.mode != LED_MODE_OFF


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
        """Fetch PLUGS_UI configuration and map its mode to an on/off state.

        Raises:
            ConfigEntryAuthFailed: If stored Shelly credentials are no longer valid.
            UpdateFailed: If the device cannot be contacted or returns bad data.
        """
        try:
            config = await self.client.async_get_led_config()
            return ShellyLedState(
                mode=led_mode_from_config(config),
                night_mode=night_mode_from_config(config),
            )
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
