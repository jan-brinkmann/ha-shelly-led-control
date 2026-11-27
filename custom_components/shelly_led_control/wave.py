"""Control the indicator intensity of Shelly Wave plugs through Z-Wave JS."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

if TYPE_CHECKING:
    from zwave_js_server.model.value import Value

ZWAVE_DOMAIN = "zwave_js"
SET_CONFIG_PARAMETER = "set_config_parameter"
LED_INTENSITY_PARAMETER = 105
WAVE_PLUG_PRODUCT_IDS = {0x0087, 0x0088, 0x0089, 0x0092}


@callback
def async_get_wave_led_parameter(hass: HomeAssistant, device_id: str) -> Value | None:
    """Return the writable intensity parameter of an interviewed Shelly Wave plug."""
    if not hass.services.has_service(ZWAVE_DOMAIN, SET_CONFIG_PARAMETER):
        return None

    from homeassistant.components.zwave_js.helpers import async_get_node_from_device_id
    from zwave_js_server.const import NodeStatus
    from zwave_js_server.model.command_class import CommandClass

    try:
        node = async_get_node_from_device_id(hass, device_id)
    except ValueError:
        return None
    if (
        node.manufacturer_id != 0x0460
        or node.product_type != 0x0002
        or node.product_id not in WAVE_PLUG_PRODUCT_IDS
        or not node.ready
        or node.status == NodeStatus.DEAD
    ):
        return None
    return next(
        (
            value
            for value in node.values.values()
            if value.command_class == CommandClass.CONFIGURATION
            and value.endpoint in (None, 0)
            and value.property_ == LED_INTENSITY_PARAMETER
            and value.property_key is None
            and value.metadata.readable
            and value.metadata.writeable
        ),
        None,
    )


class ShellyWaveLedLight(LightEntity):
    """Expose Z-Wave parameter 105 as a dimmable status LED light."""

    _attr_has_entity_name = True
    _attr_translation_key = "status_led"
    _attr_icon = "mdi:led-on"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, unique_id: str, device: DeviceEntry) -> None:
        """Associate the LED controls with the chosen Z-Wave JS device."""
        self._device_id = device.id
        self._intensity: int | None = None
        self._last_intensity = 100
        self._write_lock = asyncio.Lock()
        self._attr_unique_id = f"{unique_id}_status_led"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="Shelly",
            model=device.model,
            name=device.name_by_user or device.name,
            sw_version=device.sw_version,
        )

    @property
    def available(self) -> bool:
        """Return whether the parameter has a known intensity."""
        return self._intensity is not None

    @property
    def is_on(self) -> bool | None:
        """Return whether the indicator is configured to have a positive intensity."""
        return None if self._intensity is None else self._intensity > 0

    @property
    def brightness(self) -> int | None:
        """Scale the configured intensity to Home Assistant's brightness range."""
        return None if self._intensity is None else round(self._intensity * 255 / 100)

    async def async_update(self) -> None:
        """Read the latest reported parameter value from the Z-Wave JS cache."""
        parameter = async_get_wave_led_parameter(self.hass, self._device_id)
        value = parameter.value if parameter is not None else None
        self._intensity = value if type(value) is int and 0 <= value <= 100 else None
        if self._intensity:
            self._last_intensity = self._intensity

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set a requested brightness or restore the most recent positive value."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        intensity = (
            None if brightness is None else max(1, round(brightness * 100 / 255))
        )
        await self._async_set_intensity(intensity)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the indicator by setting its configured intensity to zero."""
        await self._async_set_intensity(0)

    async def _async_set_intensity(self, intensity: int | None) -> None:
        """Write only parameter 105 and wait for the Z-Wave JS service result."""
        async with self._write_lock:
            await self.async_update()
            if self._intensity is None:
                raise HomeAssistantError("Shelly Wave LED intensity is unavailable")
            if intensity is None:
                intensity = self._last_intensity
            if intensity != self._intensity:
                await self.hass.services.async_call(
                    ZWAVE_DOMAIN,
                    SET_CONFIG_PARAMETER,
                    {
                        "device_id": self._device_id,
                        "parameter": LED_INTENSITY_PARAMETER,
                        "value": intensity,
                    },
                    blocking=True,
                    context=self._context,
                )
            await self.async_update_ha_state(force_refresh=True)
