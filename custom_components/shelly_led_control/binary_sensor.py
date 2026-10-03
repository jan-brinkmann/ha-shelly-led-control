"""Binary sensor platform for current Shelly status LED night-mode activity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    """Add a read-only night-mode activity sensor for a configured Shelly."""
    del hass
    async_add_entities(
        [ShellyNightModeActiveSensor(entry, entry.runtime_data.coordinator)]
    )


class ShellyNightModeActiveSensor(
    CoordinatorEntity[ShellyLedCoordinator], BinarySensorEntity
):
    """Report whether enabled night mode is inside its Shelly-local time window."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:weather-night"
    _attr_translation_key = "night_mode_active"

    def __init__(
        self, entry: ShellyLedConfigEntry, coordinator: ShellyLedCoordinator
    ) -> None:
        """Initialize stable sensor and device registry metadata."""
        super().__init__(coordinator)
        device_info = entry.runtime_data.device_info
        self._attr_unique_id = f"{entry.unique_id}_night_mode_active"
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
        """Return current night-mode activity, or None when it cannot be determined."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.night_mode_active
