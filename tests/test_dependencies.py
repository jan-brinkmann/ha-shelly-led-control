"""Tests for sharing Home Assistant's managed Shelly library requirements."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.requirements import RequirementsManager
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shelly_led_control.const import DOMAIN

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


async def test_requirements_follow_official_shelly_without_configuration(
    hass: HomeAssistant,
) -> None:
    """Resolve Core's Shelly requirements without installing a competing version."""
    hass.config.skip_pip = False
    manager = RequirementsManager(hass)
    with patch.object(
        manager, "async_process_requirements", new_callable=AsyncMock
    ) as process_requirements:
        integration = await manager.async_get_integration_with_requirements(DOMAIN)

    shelly = await async_get_integration(hass, "shelly")
    assert not integration.requirements
    process_requirements.assert_any_await("shelly", shelly.requirements, True)
    assert "shelly" not in hass.config.components


async def test_setup_does_not_require_configured_official_shelly(
    hass: HomeAssistant, mock_client
) -> None:
    """Load the LED entities without forcing setup of the official integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Waschmaschine",
        unique_id="aa:bb:cc:dd:ee:ff",
        data={CONF_HOST: "192.0.2.10"},
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.shelly_led_control.ShellyLedClient",
        return_value=mock_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_client.async_connect.assert_awaited_once()
    assert "shelly" not in hass.config.components
