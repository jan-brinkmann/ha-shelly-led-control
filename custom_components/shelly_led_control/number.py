"""Number platform for Shelly status LED night-mode brightness."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity
from homeassistant.const import PERCENTAGE, EntityCategory
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
    """Add the night-mode brightness entity for a configured Shelly device."""
    del hass
    async_add_entities(
        [ShellyNightModeBrightnessNumber(entry, entry.runtime_data.coordinator)]
    )


class ShellyNightModeBrightnessNumber(
    CoordinatorEntity[ShellyLedCoordinator], NumberEntity
):
    """Expose Shelly LED night-mode brightness as a percentage setting."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_icon = "mdi:brightness-4"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "night_mode_brightness"

    def __init__(
        self, entry: ShellyLedConfigEntry, coordinator: ShellyLedCoordinator
    ) -> None:
        """Initialize stable entity and device registry metadata."""
        super().__init__(coordinator)
        device_info = entry.runtime_data.device_info
        self._attr_unique_id = f"{entry.unique_id}_night_mode_brightness"
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
    def native_value(self) -> float | None:
        """Return the configured percentage, or None if it has not been reported."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.night_mode.brightness

    async def async_set_native_value(self, value: float) -> None:
        """Set night-mode brightness in percent and refresh the device state.

        Raises:
            HomeAssistantError: If the value is invalid or the device update fails.
        """
        await self.coordinator.async_set_night_mode_brightness(value)
