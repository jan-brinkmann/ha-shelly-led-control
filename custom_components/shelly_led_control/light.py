"""Light platform for Shelly status LED indication."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.light import ColorMode, LightEntity
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
    """Add the single status LED light for a configured Shelly device."""
    del hass
    async_add_entities([ShellyStatusLedLight(entry, entry.runtime_data.coordinator)])


class ShellyStatusLedLight(CoordinatorEntity[ShellyLedCoordinator], LightEntity):
    """Expose one Shelly PLUGS_UI LED indication as an on/off light."""

    _attr_has_entity_name = True
    _attr_color_mode = ColorMode.ONOFF
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:led-on"
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_translation_key = "status_led"

    def __init__(
        self, entry: ShellyLedConfigEntry, coordinator: ShellyLedCoordinator
    ) -> None:
        """Initialize stable entity and device registry metadata."""
        super().__init__(coordinator)
        device_info = entry.runtime_data.device_info
        self._attr_unique_id = f"{entry.unique_id}_status_led"
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
        """Return the state derived from the current PLUGS_UI mode."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable Shelly LED indication without accepting unsupported features."""
        del kwargs
        await self.coordinator.async_set_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable Shelly LED indication without accepting unsupported features."""
        del kwargs
        await self.coordinator.async_set_enabled(False)
