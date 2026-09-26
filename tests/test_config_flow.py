"""Tests for the Shelly Status LED Control configuration flow."""

from unittest.mock import AsyncMock, patch

import pytest
from aioshelly.exceptions import DeviceConnectionError
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from custom_components.shelly_led_control.api import ShellyDeviceInfo
from custom_components.shelly_led_control.const import DOMAIN

TEST_MAC = "aa:bb:cc:dd:ee:ff"

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.mark.asyncio
async def test_user_flow_creates_entry(hass) -> None:
    """Create a config entry after validating a supported Shelly device."""
    device_info = ShellyDeviceInfo(
        mac=TEST_MAC,
        model="SNSW-001P16EU",
        name="Waschmaschine",
        firmware_version="1.6.1",
    )
    user_input = {
        CONF_HOST: "192.0.2.10",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "secret",
    }

    with (
        patch(
            "custom_components.shelly_led_control.config_flow.async_validate_input",
            new=AsyncMock(return_value=device_info),
        ),
        patch(
            "custom_components.shelly_led_control.async_setup_entry",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=user_input
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "Waschmaschine"
    assert result["data"] == {**user_input, "mac": TEST_MAC}


@pytest.mark.asyncio
async def test_user_flow_reports_unreachable_device(hass) -> None:
    """Keep the form open and show an error when the device is unreachable."""
    with patch(
        "custom_components.shelly_led_control.config_flow.async_validate_input",
        new=AsyncMock(side_effect=DeviceConnectionError("unavailable")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={CONF_HOST: "192.0.2.10", CONF_USERNAME: "admin", CONF_PASSWORD: ""},
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}
