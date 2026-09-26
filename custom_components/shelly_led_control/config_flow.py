"""Config flow for Shelly LED Control."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.device_registry import format_mac

from .api import ShellyDeviceInfo, ShellyLedClient, ShellyUnsupportedDeviceError
from .const import DOMAIN


async def async_validate_input(
    flow: ConfigFlow,
    host: str,
    username: str | None,
    password: str | None,
) -> ShellyDeviceInfo:
    """Validate user input against a Shelly and return its stable metadata.

    The temporary client is always disconnected before the config flow proceeds;
    setup creates the persistent connection used by the entity.
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
            except ShellyUnsupportedDeviceError:
                errors["base"] = "unsupported_device"
            except RpcCallError:
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
            step_id="user",
            data_schema=self._user_schema(user_input),
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
        if username is not None and password is not None:
            data[CONF_USERNAME] = username
            data[CONF_PASSWORD] = password
        return data
