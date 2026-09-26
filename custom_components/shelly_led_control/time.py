"""Time platform for Shelly status LED night mode."""

from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ShellyLedCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import ShellyLedConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ShellyLedConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the night-mode start and end time entities for a Shelly device."""
    del hass
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            ShellyNightModeStartTime(entry, coordinator),
            ShellyNightModeEndTime(entry, coordinator),
        ]
    )


class _ShellyNightModeTimeEntity(CoordinatorEntity[ShellyLedCoordinator], TimeEntity):
    """Provide shared device metadata and availability for night-mode times."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _unique_id_suffix: str

    def __init__(
        self, entry: ShellyLedConfigEntry, coordinator: ShellyLedCoordinator
    ) -> None:
        """Initialize stable entity and device registry metadata."""
        super().__init__(coordinator)
        device_info = entry.runtime_data.device_info
        self._attr_unique_id = f"{entry.unique_id}_{self._unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            connections={(CONNECTION_NETWORK_MAC, device_info.mac)},
            manufacturer="Shelly",
            model=device_info.model,
            name=device_info.name,
            sw_version=device_info.firmware_version,
        )

    @property
    def available(self) -> bool:
        """Return whether both the coordinator and Shelly RPC link are available."""
        return super().available and self.coordinator.client.connected


class ShellyNightModeStartTime(_ShellyNightModeTimeEntity):
    """Expose the start of the Shelly LED night-mode time window."""

    _attr_translation_key = "night_mode_start"
    _unique_id_suffix = "night_mode_start"

    @property
    def native_value(self) -> time | None:
        """Return the configured local night-mode start time."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.night_mode.start

    async def async_set_value(self, value: time) -> None:
        """Set the local night-mode start time on the Shelly device."""
        await self.coordinator.async_set_night_mode_start(value)


class ShellyNightModeEndTime(_ShellyNightModeTimeEntity):
    """Expose the end of the Shelly LED night-mode time window."""

    _attr_translation_key = "night_mode_end"
    _unique_id_suffix = "night_mode_end"

    @property
    def native_value(self) -> time | None:
        """Return the configured local night-mode end time."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.night_mode.end

    async def async_set_value(self, value: time) -> None:
        """Set the local night-mode end time on the Shelly device."""
        await self.coordinator.async_set_night_mode_end(value)
