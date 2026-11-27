"""Set up the Shelly LED Control integration."""

from __future__ import annotations

from dataclasses import dataclass

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import device_registry as dr

from .api import ShellyDeviceInfo, ShellyLedClient, ShellyUnsupportedDeviceError
from .coordinator import ShellyLedCoordinator

PLATFORMS: tuple[Platform, ...] = (
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
)


@dataclass(slots=True)
class RuntimeData:
    """Hold the runtime objects owned by one config entry."""

    client: ShellyLedClient
    coordinator: ShellyLedCoordinator
    device_info: ShellyDeviceInfo


type ShellyLedConfigEntry = ConfigEntry[RuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: ShellyLedConfigEntry) -> bool:
    """Set up Shelly LED Control from a config entry.

    Connect to the device and start the platforms supported by its LED API.
    """
    if CONF_DEVICE_ID in entry.data:
        if dr.async_get(hass).async_get(entry.data[CONF_DEVICE_ID]) is None:
            raise ConfigEntryError(
                "The selected Z-Wave JS device is no longer registered"
            )
        await hass.config_entries.async_forward_entry_setups(entry, (Platform.LIGHT,))
        return True

    client = ShellyLedClient(
        hass,
        entry.data[CONF_HOST],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
    )

    try:
        device_info = await client.async_connect()
    except InvalidAuthError as err:
        raise ConfigEntryAuthFailed("Invalid Shelly credentials") from err
    except DeviceConnectionError as err:
        raise ConfigEntryNotReady("Unable to connect to the Shelly device") from err
    except ShellyUnsupportedDeviceError as err:
        raise ConfigEntryError(
            "The device does not provide compatible LED controls"
        ) from err
    except RpcCallError as err:
        raise ConfigEntryNotReady("Unable to initialize the Shelly RPC API") from err

    coordinator = ShellyLedCoordinator(hass, entry, client, device_info)
    try:
        await coordinator.async_config_entry_first_refresh()
    except (ConfigEntryAuthFailed, ConfigEntryNotReady, ConfigEntryError):
        await client.async_disconnect()
        raise

    entry.runtime_data = RuntimeData(client, coordinator, device_info)
    platforms = (Platform.LIGHT,) if device_info.legacy_leds else PLATFORMS
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ShellyLedConfigEntry) -> bool:
    """Unload a Shelly LED Control config entry and its connection."""
    if CONF_DEVICE_ID in entry.data:
        return await hass.config_entries.async_unload_platforms(
            entry, (Platform.LIGHT,)
        )

    platforms = (
        (Platform.LIGHT,) if entry.runtime_data.device_info.legacy_leds else PLATFORMS
    )
    unloaded = await hass.config_entries.async_unload_platforms(entry, platforms)
    if unloaded:
        entry.runtime_data.coordinator.async_cancel_scheduled_updates()
        await entry.runtime_data.client.async_disconnect()
    return unloaded
