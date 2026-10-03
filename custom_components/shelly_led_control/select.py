"""Select platform for Shelly LED indication mode."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENABLED_LED_MODES
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
    """Add the indication-mode setting for a configured Shelly device."""
    del hass
    async_add_entities([ShellyLedModeSelect(entry, entry.runtime_data.coordinator)])


class ShellyLedModeSelect(CoordinatorEntity[ShellyLedCoordinator], SelectEntity):
    """Select an enabled LED mode; disabled indication has no selected option."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:led-on"
    _attr_options = list(ENABLED_LED_MODES)
    _attr_translation_key = "led_indication_mode"

    def __init__(
        self, entry: ShellyLedConfigEntry, coordinator: ShellyLedCoordinator
    ) -> None:
        """Initialize stable entity and device registry metadata."""
        super().__init__(coordinator)
        device_info = entry.runtime_data.device_info
        self._attr_unique_id = f"{entry.unique_id}_led_indication_mode"
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
        """Require current coordinator data and a connected Shelly RPC link."""
        return super().available and self.coordinator.client.connected

    @property
    def current_option(self) -> str | None:
        """Return power/switch, or None while off, unsupported or not yet read."""
        if self.coordinator.data is None:
            return None
        mode = self.coordinator.data.mode
        return mode if mode in ENABLED_LED_MODES else None

    async def async_select_option(self, option: str) -> None:
        """Set power/switch indication and refresh; device errors propagate."""
        await self.coordinator.async_set_mode(option)
