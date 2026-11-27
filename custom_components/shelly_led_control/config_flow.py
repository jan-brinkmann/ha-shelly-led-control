"""Config flow for Shelly LED Control."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.device_registry import async_get, format_mac
from homeassistant.helpers.selector import DeviceSelector, DeviceSelectorConfig

from .api import ShellyDeviceInfo, ShellyLedClient, ShellyUnsupportedDeviceError
from .const import DOMAIN
from .wave import (
    SET_CONFIG_PARAMETER,
    ZWAVE_DOMAIN,
    async_get_wave_led_parameter,
    wave_led_supports_intensity_control,
)


async def async_validate_input(
    flow: ConfigFlow,
    host: str,
    username: str | None,
    password: str | None,
) -> ShellyDeviceInfo:
    """Validate user input against a Shelly and return its stable metadata.

    The temporary client is always disconnected before the config flow proceeds.
    """
    client = ShellyLedClient(flow.hass, host, username, password)
    try:
        return await client.async_connect()
    finally:
        await client.async_disconnect()


class ShellyLedConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle UI configuration and reauthentication for Shelly LED Control."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer Wave setup when Z-Wave JS is present, or open the Wi-Fi form."""
        if user_input is None and self.hass.services.has_service(
            ZWAVE_DOMAIN, SET_CONFIG_PARAMETER
        ):
            return self.async_show_menu(step_id="user", menu_options=["wifi", "wave"])
        return await self.async_step_wifi(user_input)

    async def async_step_wifi(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual configuration by hostname or IP address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            username = user_input.get(CONF_USERNAME, "").strip() or None
            password = user_input.get(CONF_PASSWORD, "") or None

            try:
                device_info = await async_validate_input(self, host, username, password)
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except (DeviceConnectionError, OSError, ValueError):
                errors["base"] = "cannot_connect"
            except (RpcCallError, ShellyUnsupportedDeviceError):
                errors["base"] = "unsupported_device"
            else:
                mac = format_mac(device_info.mac)
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device_info.name,
                    data=self._entry_data(host, mac, username, password),
                )

        return self.async_show_form(
            step_id="wifi",
            data_schema=self._user_schema(user_input),
            errors=errors,
        )

    async def async_step_wave(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a Z-Wave JS plug that supports switching and dimming its LED."""
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            device = async_get(self.hass).async_get(device_id)
            parameter = (
                async_get_wave_led_parameter(self.hass, device_id)
                if device is not None
                else None
            )
            if device is None or parameter is None:
                errors["base"] = "unsupported_wave_device"
            elif not wave_led_supports_intensity_control(parameter):
                errors["base"] = "unsupported_wave_led_range"
            else:
                await self.async_set_unique_id(f"zwave_{device_id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=device.name_by_user or device.name or "Shelly Wave",
                    data={CONF_DEVICE_ID: device_id},
                )

        return self.async_show_form(
            step_id="wave",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): DeviceSelector(
                        DeviceSelectorConfig(filter={"integration": ZWAVE_DOMAIN})
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication after Home Assistant reports invalid credentials."""
        del entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate replacement credentials and reload the existing config entry."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            username = user_input.get(CONF_USERNAME, "").strip() or None
            password = user_input.get(CONF_PASSWORD, "") or None
            try:
                device_info = await async_validate_input(
                    self, entry.data[CONF_HOST], username, password
                )
            except InvalidAuthError:
                errors["base"] = "invalid_auth"
            except (DeviceConnectionError, OSError, ValueError):
                errors["base"] = "cannot_connect"
            except (RpcCallError, ShellyUnsupportedDeviceError):
                errors["base"] = "unsupported_device"
            else:
                mac = format_mac(device_info.mac)
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=self._entry_data(
                        entry.data[CONF_HOST], mac, username, password
                    ),
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self._credentials_schema(entry.data),
            errors=errors,
            description_placeholders={CONF_HOST: entry.data[CONF_HOST]},
        )

    @staticmethod
    def _user_schema(user_input: Mapping[str, Any] | None) -> vol.Schema:
        """Return the manual setup form schema with safe defaults."""
        values = user_input or {}
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=values.get(CONF_HOST, "")): str,
                vol.Optional(
                    CONF_USERNAME, default=values.get(CONF_USERNAME, "admin")
                ): str,
                vol.Optional(CONF_PASSWORD, default=values.get(CONF_PASSWORD, "")): str,
            }
        )

    @staticmethod
    def _credentials_schema(entry_data: Mapping[str, Any]) -> vol.Schema:
        """Return the credential-only schema used by the reauth flow."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME, default=entry_data.get(CONF_USERNAME, "admin")
                ): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

    @staticmethod
    def _entry_data(
        host: str,
        mac: str,
        username: str | None,
        password: str | None,
    ) -> dict[str, str]:
        """Build config-entry data without persisting unused empty credentials."""
        data = {CONF_HOST: host, "mac": mac}
        if password is not None:
            data[CONF_USERNAME] = username or "admin"
            data[CONF_PASSWORD] = password
        return data
