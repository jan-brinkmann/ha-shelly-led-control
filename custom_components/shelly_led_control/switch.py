"""Switch platform for Shelly status LED night mode."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.switch import SwitchEntity
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
    """Add the night-mode switch for a configured Shelly device."""
    del hass
    async_add_entities([ShellyNightModeSwitch(entry, entry.runtime_data.coordinator)])


class ShellyNightModeSwitch(CoordinatorEntity[ShellyLedCoordinator], SwitchEntity):
    """Expose Shelly LED night mode as a configuration switch."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_icon = "mdi:weather-night"
    _attr_translation_key = "night_mode"

    def __init__(
        self, entry: ShellyLedConfigEntry, coordinator: ShellyLedCoordinator
    ) -> None:
        """Initialize stable entity and device registry metadata."""
        super().__init__(coordinator)
        device_info = entry.runtime_data.device_info
        self._attr_unique_id = f"{entry.unique_id}_night_mode"
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

    @property
    def is_on(self) -> bool | None:
        """Return whether night mode is enabled in the current configuration."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.night_mode.enabled

    async def async_turn_on(self, **kwargs: object) -> None:
        """Enable Shelly LED night mode."""
        del kwargs
        await self.coordinator.async_set_night_mode_enabled(True)

    async def async_turn_off(self, **kwargs: object) -> None:
        """Disable Shelly LED night mode."""
        del kwargs
        await self.coordinator.async_set_night_mode_enabled(False)
