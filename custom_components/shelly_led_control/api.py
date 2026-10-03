"""Asynchronous Shelly Gen2 RPC access for status LED control."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import time
from typing import Any

from aioshelly.common import ConnectionOptions
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
from aioshelly.rpc_device import RpcDevice, RpcUpdateType
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .const import DEFAULT_ENABLED_LED_MODE, LED_MODE_OFF, RPC_TIMEOUT


class ShellyUnsupportedDeviceError(Exception):
    """Raise when the connected Shelly does not expose the required component."""


@dataclass(frozen=True, slots=True)
class ShellyDeviceInfo:
    """Describe the hardware information needed by the integration."""

    mac: str
    model: str
    name: str
    firmware_version: str


@dataclass(frozen=True, slots=True)
class ShellyNightMode:
    """Represent the configurable Shelly LED night mode."""

    enabled: bool
    start: time
    end: time
    brightness: float | None

    def is_active_at(self, value: time) -> bool:
        """Return whether enabled night mode applies at a Shelly-local time.

        The start is inclusive and the end exclusive, including windows across
        midnight. Equal start and end times apply all day. Brightness does not
        affect whether night mode is active.
        """
        if not self.enabled:
            return False
        if self.start == self.end:
            return True
        if self.start < self.end:
            return self.start <= value < self.end
        return value >= self.start or value < self.end

    def hides_led_at(self, value: time) -> bool:
        """Return whether active night mode suppresses the LED at a local time.

        A night-mode brightness of zero turns off the physical LED while
        preserving its configured indication mode.
        """
        return self.brightness == 0 and self.is_active_at(value)


def led_mode_from_config(config: dict[str, Any]) -> str:
    """Return the PLUGS_UI LED mode from a component configuration.

    Raises:
        ShellyUnsupportedDeviceError: If the response has no valid LED mode.
    """
    leds = config.get("leds")
    if not isinstance(leds, dict) or not isinstance(mode := leds.get("mode"), str):
        raise ShellyUnsupportedDeviceError("PLUGS_UI configuration has no LED mode")
    return mode


def led_brightness_from_config(
    config: dict[str, Any], switch_output: bool | None
) -> float | None:
    """Return normal LED brightness for the configured mode and relay output.

    Brightness comes from ``colors.power`` or the selected ``colors.switch:0``
    state. Missing, invalid or unsupported settings return None without
    preventing other entities from updating. Night mode is applied separately.
    """
    leds = config.get("leds")
    if not isinstance(leds, dict):
        return None
    if leds.get("mode") == LED_MODE_OFF:
        return 0
    settings = _led_brightness_settings_from_config(config, switch_output)
    if settings is None:
        return None
    brightness = settings.get("brightness")
    if (
        isinstance(brightness, bool)
        or not isinstance(brightness, int | float)
        or not 0 <= brightness <= 100
    ):
        return None
    return brightness


def _led_brightness_settings_from_config(
    config: dict[str, Any], switch_output: bool | None
) -> dict[str, Any] | None:
    """Return the current normal-brightness settings without copying or mutating.

    Disabled or unsupported modes, unknown relay output and malformed color
    branches return None. A missing brightness field can be added by a writer.
    """
    leds = config.get("leds")
    if not isinstance(leds, dict):
        return None
    colors = leds.get("colors")
    if not isinstance(colors, dict):
        return None
    if leds.get("mode") == "power":
        settings = colors.get("power")
    elif leds.get("mode") == "switch" and isinstance(switch_output, bool):
        switch_colors = colors.get("switch:0")
        if not isinstance(switch_colors, dict):
            return None
        settings = switch_colors.get("on" if switch_output else "off")
    else:
        return None
    return settings if isinstance(settings, dict) else None


def _switch_output_from_status(status: object) -> bool | None:
    """Return a relay output flag, or None for missing or invalid status data."""
    if not isinstance(status, dict):
        return None
    output = status.get("output")
    return output if isinstance(output, bool) else None


def night_mode_from_config(config: dict[str, Any]) -> ShellyNightMode:
    """Return the night-mode settings from a PLUGS_UI configuration.

    Raises:
        ShellyUnsupportedDeviceError: If the response has no valid night mode.
    """
    leds = config.get("leds")
    if not isinstance(leds, dict) or not isinstance(
        night_mode := leds.get("night_mode"), dict
    ):
        raise ShellyUnsupportedDeviceError("PLUGS_UI configuration has no night mode")

    enabled = night_mode.get("enable")
    active_between = night_mode.get("active_between")
    brightness = night_mode.get("brightness")
    if not isinstance(enabled, bool) or not (
        isinstance(active_between, list)
        and len(active_between) == 2
        and all(isinstance(value, str) for value in active_between)
    ):
        raise ShellyUnsupportedDeviceError("PLUGS_UI night mode has invalid settings")
    if brightness is not None and (
        isinstance(brightness, bool)
        or not isinstance(brightness, int | float)
        or not 0 <= brightness <= 100
    ):
        raise ShellyUnsupportedDeviceError("PLUGS_UI night mode has invalid brightness")

    return ShellyNightMode(
        enabled=enabled,
        start=_time_from_rpc(active_between[0]),
        end=_time_from_rpc(active_between[1]),
        brightness=brightness,
    )


def _time_from_rpc(value: str) -> time:
    """Convert a Shelly ``HH:MM`` value into a Python time.

    Raises:
        ShellyUnsupportedDeviceError: If the value is not an RFC-compatible
            Shelly night-mode time.
    """
    if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value) is None:
        raise ShellyUnsupportedDeviceError(
            "PLUGS_UI night mode time is not in HH:MM format"
        )
    return time.fromisoformat(value)


def _time_to_rpc(value: time) -> str:
    """Convert a Home Assistant time value into Shelly's ``HH:MM`` format.

    Raises:
        ValueError: If the value has a resolution below one minute.
    """
    if value.second or value.microsecond:
        raise ValueError("Shelly night mode supports whole-minute times only")
    return value.strftime("%H:%M")


class ShellyLedClient:
    """Maintain an authenticated local RPC connection to one Shelly device."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str | None,
        password: str | None,
    ) -> None:
        """Initialize the client without opening a network connection."""
        self._hass = hass
        self._host = host
        self._username = username or None
        self._password = password or None
        self._device: RpcDevice | None = None
        self._device_info: ShellyDeviceInfo | None = None
        self._last_enabled_mode: str | None = None
        self._last_switch_output: bool | None = None
        self._command_lock = asyncio.Lock()
        self._refresh_callback: Callable[[], Awaitable[None]] | None = None
        self._availability_callback: Callable[[], None] | None = None

    @property
    def connected(self) -> bool:
        """Return whether the persistent RPC connection is currently available."""
        return self._device is not None and self._device.connected

    @property
    def device_info(self) -> ShellyDeviceInfo:
        """Return discovered device metadata after a successful connection.

        Raises:
            RuntimeError: If called before :meth:`async_connect` succeeds.
        """
        if self._device_info is None:
            raise RuntimeError("Shelly device metadata is not available")
        return self._device_info

    async def async_connect(self) -> ShellyDeviceInfo:
        """Connect to the device and verify support for ``PLUGS_UI``.

        Returns:
            Stable device metadata read from the Shelly RPC API.

        Raises:
            DeviceConnectionError: If the local RPC connection cannot be opened.
            InvalidAuthError: If configured credentials are rejected.
            ShellyUnsupportedDeviceError: If ``PLUGS_UI`` is unavailable.
        """
        options = ConnectionOptions(
            self._host,
            self._username,
            self._password,
            device_mac=None,
        )
        device = await RpcDevice.create(
            async_get_clientsession(self._hass), None, options
        )
        try:
            await device.initialize()
            config = await device.call_rpc("PLUGS_UI.GetConfig", timeout=RPC_TIMEOUT)
            mode = led_mode_from_config(config)
        except (DeviceConnectionError, InvalidAuthError, RpcCallError):
            await device.shutdown()
            raise
        except ShellyUnsupportedDeviceError:
            await device.shutdown()
            raise

        mac = device.shelly.get("mac")
        if not isinstance(mac, str) or not mac:
            await device.shutdown()
            raise ShellyUnsupportedDeviceError("Shelly did not return a MAC address")

        self._device = device
        self._device_info = ShellyDeviceInfo(
            mac=format_mac(mac),
            model=device.model,
            name=device.name,
            firmware_version=device.version,
        )
        if mode != LED_MODE_OFF:
            self._last_enabled_mode = mode
        self._last_switch_output = _switch_output_from_status(
            device.status.get("switch:0")
        )
        device.subscribe_updates(self._async_handle_rpc_update)
        return self._device_info

    async def async_disconnect(self) -> None:
        """Close the persistent RPC connection and discard its device object."""
        if self._device is not None:
            await self._device.shutdown()
            self._device = None

    def async_set_callbacks(
        self,
        refresh_callback: Callable[[], Awaitable[None]],
        availability_callback: Callable[[], None],
    ) -> None:
        """Register callbacks for configuration, relay and connection changes."""
        self._refresh_callback = refresh_callback
        self._availability_callback = availability_callback

    async def async_get_led_config(self) -> dict[str, Any]:
        """Fetch the current ``PLUGS_UI`` configuration from the device.

        Returns:
            The complete component configuration so callers can preserve fields
            that are outside the requested LED or night-mode change.
        """
        device = self._require_device()
        config = await device.call_rpc("PLUGS_UI.GetConfig", timeout=RPC_TIMEOUT)
        mode = led_mode_from_config(config)
        if mode != LED_MODE_OFF:
            self._last_enabled_mode = mode
        return config

    async def async_get_device_time(self) -> time | None:
        """Return the current local time reported by the Shelly.

        The optional ``unixtime`` status value supplies the seconds component,
        allowing callers to schedule a refresh at a night-mode boundary without
        waiting for the remainder of the current minute. ``None`` means the
        device has not synchronized its clock yet, so a time-based effective
        LED state cannot be determined safely.
        """
        device = self._require_device()
        status = await device.call_rpc("Sys.GetStatus", timeout=RPC_TIMEOUT)
        if not isinstance(status, dict):
            raise ShellyUnsupportedDeviceError("Sys status is not an object")
        value = status.get("time")
        if value is None:
            return None
        if not isinstance(value, str):
            raise ShellyUnsupportedDeviceError("Sys status has invalid local time")
        device_time = _time_from_rpc(value)
        unix_time = status.get("unixtime")
        if isinstance(unix_time, int | float) and not isinstance(unix_time, bool):
            return device_time.replace(second=int(unix_time) % 60)
        return device_time

    async def async_get_switch_output(self) -> bool | None:
        """Read the relay output for switch-mode brightness, also on fallback polls.

        Missing or invalid output is unknown. Connection and RPC failures
        propagate to the coordinator so it can mark device data unavailable.
        """
        device = self._require_device()
        status = await device.call_rpc(
            "Switch.GetStatus", {"id": 0}, timeout=RPC_TIMEOUT
        )
        self._last_switch_output = _switch_output_from_status(status)
        return self._last_switch_output

    async def async_set_led_enabled(self, enabled: bool) -> None:
        """Enable or disable LED indication while retaining related settings.

        ``False`` writes ``mode: off``. ``True`` restores the last observed
        enabled mode during this runtime, or uses ``switch`` after a restart
        when that earlier mode cannot be known from an ``off`` configuration.
        """
        async with self._command_lock:
            config = await self.async_get_led_config()
            current_mode = led_mode_from_config(config)
            if current_mode != LED_MODE_OFF:
                self._last_enabled_mode = current_mode

            target_mode = (
                self._last_enabled_mode or DEFAULT_ENABLED_LED_MODE
                if enabled
                else LED_MODE_OFF
            )
            if current_mode == target_mode:
                return

            updated_config = deepcopy(config)
            updated_leds = dict(updated_config["leds"])
            updated_leds["mode"] = target_mode
            updated_config["leds"] = updated_leds

            device = self._require_device()
            await device.call_rpc(
                "PLUGS_UI.SetConfig",
                {"config": updated_config},
                timeout=RPC_TIMEOUT,
            )
            if target_mode != LED_MODE_OFF:
                self._last_enabled_mode = target_mode

    async def async_set_led_brightness(self, value: float) -> None:
        """Set normal brightness for the current LED mode and relay state.

        Read the latest configuration and, in switch mode, the relay output
        under the command lock. Change only the selected brightness field,
        preserving the other relay state, colors, mode and night-mode settings.

        Args:
            value: The normal LED brightness from 0 to 100 percent inclusive.

        Raises:
            ValueError: If the percentage is invalid.
            ShellyUnsupportedDeviceError: If no brightness branch can be selected.
            DeviceConnectionError: If the device cannot be contacted.
            InvalidAuthError: If credentials are rejected.
            RpcCallError: If the device rejects an RPC request.
        """
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not 0 <= value <= 100
        ):
            raise ValueError("Shelly LED brightness must be between 0 and 100")
        async with self._command_lock:
            config = await self.async_get_led_config()
            mode = led_mode_from_config(config)
            switch_output = (
                await self.async_get_switch_output() if mode == "switch" else None
            )
            updated_config = deepcopy(config)
            settings = _led_brightness_settings_from_config(
                updated_config, switch_output
            )
            if settings is None:
                raise ShellyUnsupportedDeviceError(
                    "PLUGS_UI has no selectable normal brightness setting"
                )
            settings["brightness"] = value
            device = self._require_device()
            await device.call_rpc(
                "PLUGS_UI.SetConfig",
                {"config": updated_config},
                timeout=RPC_TIMEOUT,
            )

    async def async_set_night_mode_enabled(self, enabled: bool) -> None:
        """Enable or disable night mode without changing its time window."""
        await self._async_update_night_mode(enabled=enabled)

    async def async_set_night_mode_brightness(self, value: float) -> None:
        """Set night-mode brightness while preserving all other settings.

        Args:
            value: The LED brightness in percent, from 0 to 100 inclusive.

        Raises:
            ValueError: If the value is not a number in the supported range.
        """
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not 0 <= value <= 100
        ):
            raise ValueError("Shelly night mode brightness must be between 0 and 100")
        await self._async_update_night_mode(brightness=value)

    async def async_set_night_mode_start(self, value: time) -> None:
        """Set the start of the night-mode time window.

        Args:
            value: A whole-minute local time accepted by the Shelly API.
        """
        await self._async_update_night_mode(start=value)

    async def async_set_night_mode_end(self, value: time) -> None:
        """Set the end of the night-mode time window.

        Args:
            value: A whole-minute local time accepted by the Shelly API.
        """
        await self._async_update_night_mode(end=value)

    async def _async_update_night_mode(
        self,
        *,
        enabled: bool | None = None,
        brightness: float | None = None,
        start: time | None = None,
        end: time | None = None,
    ) -> None:
        """Apply selected night-mode fields while preserving all other settings."""
        async with self._command_lock:
            config = await self.async_get_led_config()
            night_mode = night_mode_from_config(config)
            updated_config = deepcopy(config)
            updated_leds = dict(updated_config["leds"])
            updated_night_mode = dict(updated_leds["night_mode"])
            updated_night_mode["enable"] = (
                night_mode.enabled if enabled is None else enabled
            )
            if brightness is not None:
                updated_night_mode["brightness"] = brightness
            updated_night_mode["active_between"] = [
                _time_to_rpc(night_mode.start if start is None else start),
                _time_to_rpc(night_mode.end if end is None else end),
            ]
            updated_leds["night_mode"] = updated_night_mode
            updated_config["leds"] = updated_leds

            device = self._require_device()
            await device.call_rpc(
                "PLUGS_UI.SetConfig",
                {"config": updated_config},
                timeout=RPC_TIMEOUT,
            )

    def _require_device(self) -> RpcDevice:
        """Return the initialized device or raise a connection error."""
        if self._device is None or not self._device.connected:
            raise DeviceConnectionError("Shelly RPC connection is unavailable")
        return self._device

    @callback
    def _async_handle_rpc_update(
        self, device: RpcDevice, update_type: RpcUpdateType
    ) -> None:
        """Refresh on configuration or relay changes and report disconnection.

        Ignore status notifications that only change power readings, avoiding
        repeated RPC refreshes while the relay output remains unchanged.
        """
        if update_type is RpcUpdateType.DISCONNECTED:
            if self._availability_callback is not None:
                self._availability_callback()
            return

        if update_type is RpcUpdateType.STATUS:
            output = _switch_output_from_status(device.status.get("switch:0"))
            if output == self._last_switch_output:
                return
            self._last_switch_output = output
            refresh = True
        else:
            refresh = (
                update_type is RpcUpdateType.EVENT
                and self._event_reports_plugs_ui_config_change()
            )
        if refresh and self._refresh_callback is not None:
            self._hass.async_create_task(
                self._refresh_callback(), "refresh Shelly LED configuration"
            )

    def _event_reports_plugs_ui_config_change(self) -> bool:
        """Return whether the latest Shelly event reports a PLUGS_UI config change."""
        if self._device is None or (event := self._device.event) is None:
            return False

        events = event.get("events")
        if not isinstance(events, list):
            return False
        return any(
            isinstance(item, dict)
            and item.get("component") == "PLUGS_UI"
            and item.get("event") == "config_changed"
            for item in events
        )
