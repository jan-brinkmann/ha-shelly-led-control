"""Set up the Shelly LED Control integration."""

from __future__ import annotations

from dataclasses import dataclass

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)

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

    The function establishes one local RPC connection, verifies that the
    device exposes ``PLUGS_UI``, and starts the entity platforms.
    """
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
        raise ConfigEntryError("The device does not provide PLUGS_UI") from err
    except RpcCallError as err:
        raise ConfigEntryNotReady("Unable to initialize the Shelly RPC API") from err

    coordinator = ShellyLedCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except (ConfigEntryAuthFailed, ConfigEntryNotReady, ConfigEntryError):
        await client.async_disconnect()
        raise

    entry.runtime_data = RuntimeData(client, coordinator, device_info)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ShellyLedConfigEntry) -> bool:
    """Unload a Shelly LED Control config entry and its RPC connection."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.coordinator.async_cancel_scheduled_updates()
        await entry.runtime_data.client.async_disconnect()
    return unloaded
