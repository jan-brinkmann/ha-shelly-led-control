"""Sensor platform for the effective Shelly status LED brightness."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE
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
    """Add a read-only brightness sensor eligible for history and statistics."""
    del hass
    async_add_entities(
        [ShellyStatusLedBrightnessSensor(entry, entry.runtime_data.coordinator)]
    )


class ShellyStatusLedBrightnessSensor(
    CoordinatorEntity[ShellyLedCoordinator], SensorEntity
):
    """Report current LED brightness derived from settings and device state."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:brightness-percent"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "status_led_brightness"

    def __init__(
        self, entry: ShellyLedConfigEntry, coordinator: ShellyLedCoordinator
    ) -> None:
        """Initialize stable sensor and device registry metadata."""
        super().__init__(coordinator)
        device_info = entry.runtime_data.device_info
        self._attr_unique_id = f"{entry.unique_id}_status_led_brightness"
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
        """Return effective brightness in percent, or None when it is unknown."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.brightness
