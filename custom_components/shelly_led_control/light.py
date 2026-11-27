"""Light platform for Shelly status indication and color presets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_DEVICE_ID, EntityCategory
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, async_get
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import ShellySwitchLedSettings
from .const import DOMAIN
from .coordinator import ShellyLedCoordinator
from .wave import ShellyWaveLedLight

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from . import ShellyLedConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ShellyLedConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the status indicators and color presets supported by this Shelly."""
    if CONF_DEVICE_ID in entry.data:
        device = async_get(hass).async_get(entry.data[CONF_DEVICE_ID])
        if device is not None and entry.unique_id is not None:
            async_add_entities([ShellyWaveLedLight(entry.unique_id, device)], True)
        return

    coordinator = entry.runtime_data.coordinator
    device_info = entry.runtime_data.device_info
    if device_info.legacy_leds:
        async_add_entities(
            ShellyStatusLedLight(entry, coordinator, legacy_setting=setting)
            for setting in device_info.legacy_leds
        )
        return
    lights = [
        ShellyStatusLedLight(entry, coordinator),
        ShellySwitchLedColorLight(entry, coordinator, True),
    ]
    if device_info.has_relay:
        lights.append(ShellySwitchLedColorLight(entry, coordinator, False))
    async_add_entities(lights)


class ShellyStatusLedLight(CoordinatorEntity[ShellyLedCoordinator], LightEntity):
    """Expose one Shelly status indication setting as an on/off light."""

    _attr_has_entity_name = True
    _attr_color_mode = ColorMode.ONOFF
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:led-on"
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_translation_key = "status_led"

    def __init__(
        self,
        entry: ShellyLedConfigEntry,
        coordinator: ShellyLedCoordinator,
        *,
        legacy_setting: str | None = None,
    ) -> None:
        """Bind the light to RPC indication or to one Gen1 LED setting."""
        super().__init__(coordinator)
        device_info = entry.runtime_data.device_info
        self._legacy_setting = legacy_setting
        if legacy_setting:
            self._attr_translation_key = (
                "network_led"
                if legacy_setting == "led_status_disable"
                else "output_led"
            )
        self._attr_unique_id = f"{entry.unique_id}_{self._attr_translation_key}"
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
        """Require a reachable device and a reported setting for Gen1 indicators."""
        return (
            super().available
            and self.coordinator.client.connected
            and (self._legacy_setting is None or self.is_on is not None)
        )

    @property
    def is_on(self) -> bool | None:
        """Return effective RPC indication or the Gen1 indicator's enable setting."""
        if self.coordinator.data is None:
            return None
        if self._legacy_setting is not None:
            return (self.coordinator.data.legacy_leds or {}).get(self._legacy_setting)
        return self.coordinator.data.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable Shelly LED indication without accepting unsupported features."""
        del kwargs
        await self.coordinator.async_set_enabled(True, setting=self._legacy_setting)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable Shelly LED indication without accepting unsupported features."""
        del kwargs
        await self.coordinator.async_set_enabled(False, setting=self._legacy_setting)


class ShellySwitchLedColorLight(ShellyStatusLedLight):
    """Configure an output preset's normal RGB/brightness, independent of activity.

    The preset's light state reflects its normal brightness, not the physical
    relay or night mode. It is available only in switch indication mode.
    """

    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_icon = "mdi:palette"

    def __init__(
        self,
        entry: ShellyLedConfigEntry,
        coordinator: ShellyLedCoordinator,
        switch_output: bool,
    ) -> None:
        """Bind a preset to the relay state or the power meter's single preset."""
        super().__init__(entry, coordinator)
        self._switch_output = switch_output
        self._attr_translation_key = (
            "switch_on_color" if switch_output else "switch_off_color"
        )
        self._attr_unique_id = f"{entry.unique_id}_{self._attr_translation_key}"
        if not entry.runtime_data.device_info.has_relay:
            self._attr_translation_key = "custom_led_color"

    @property
    def _settings(self) -> ShellySwitchLedSettings | None:
        """Return this relay state's latest preset, or None when absent."""
        if self.coordinator.data is None:
            return None
        return (
            self.coordinator.data.switch_on_settings
            if self._switch_output
            else self.coordinator.data.switch_off_settings
        )

    @property
    def available(self) -> bool:
        """Require switch indication mode and this state's configuration branch."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.mode == "switch"
            and self._settings is not None
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether the preset's normal brightness is positive, if known."""
        settings = self._settings
        if settings is None or settings.brightness is None:
            return None
        return settings.brightness > 0

    @property
    def brightness(self) -> int | None:
        """Scale normal brightness from Shelly percentages to Home Assistant."""
        settings = self._settings
        if settings is None or settings.brightness is None:
            return None
        if settings.brightness == 0:
            return 0
        return max(1, round(settings.brightness * 255 / 100))

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Scale Shelly RGB percentages to 0–255 without brightness normalization."""
        settings = self._settings
        if settings is None or settings.rgb is None:
            return None
        red, green, blue = settings.rgb
        return tuple(round(value * 255 / 100) for value in (red, green, blue))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Write supplied color/brightness, preserving omitted preset fields.

        With no fields, enable a zero-brightness preset at 100%. Color-only
        updates preserve brightness. Device errors propagate from the coordinator.
        """
        rgb = None
        if (color := kwargs.get(ATTR_RGB_COLOR)) is not None:
            red, green, blue = color
            rgb = tuple(round(value * 100 / 255, 2) for value in (red, green, blue))
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        await self.coordinator.async_set_switch_settings(
            self._switch_output,
            rgb=rgb,
            brightness=(
                round(brightness * 100 / 255, 2) if brightness is not None else None
            ),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set only this preset's brightness to zero, preserving RGB and LED mode."""
        del kwargs
        await self.coordinator.async_set_switch_settings(
            self._switch_output, brightness=0
        )
