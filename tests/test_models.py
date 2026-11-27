"""Exercise the setup and LED controls for the different Shelly plug APIs."""

from base64 import b64encode
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aioshelly.exceptions import RpcCallError
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.shelly_led_control.api import ShellyLedClient
from custom_components.shelly_led_control.const import DOMAIN, RPC_TIMEOUT

HOST = "192.0.2.10"
MAC = "aa:bb:cc:dd:ee:ff"
pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.mark.parametrize(
    ("model", "component", "generation"),
    [
        ("SNPL-00112EU", "PLUGS_UI", 2),
        ("SNPL-10112EU", "PLUGS_UI", 2),
        ("SNPL-00112UK", "PLUGUK_UI", 2),
        ("S3PL-00112EU", "PLUGS_UI", 3),
        ("S3PL-10112EU", "PLUGS_UI", 3),
        ("S3PL-20112EU", "PLUGS_UI", 3),
        ("S3PL-30110EU", "PLUGS_UI", 3),
        ("S3PL-30116EU", "PLUGPM_UI", 3),
        ("S4PL-00116US", "PLUGS_UI", 4),
    ],
)
async def test_rpc_models(
    hass, aioclient_mock, led_config, model, component, generation
):
    """Use each model's RPC namespace for reads and writes through Home Assistant."""
    meter = component == "PLUGPM_UI"
    colors = led_config["leds"]["colors"]
    if meter:
        colors["pm1:0"] = {"on": colors.pop("switch:0")["on"]}
    led_config["leds"]["mode"] = "switch"
    aioclient_mock.get(
        f"http://{HOST}/shelly", json={"gen": generation, "model": model}
    )

    async def rpc(method, params=None, **kwargs):
        """Return documented component data and persist only matching LED writes."""
        if method == f"{component}.GetConfig":
            return deepcopy(led_config)
        if method == f"{component}.SetConfig":
            led_config.update(deepcopy(params["config"]))
            return {}
        if method == "Sys.GetStatus":
            return {"time": "12:00"}
        if method == "Switch.GetStatus" and not meter:
            return {"output": True}
        raise AssertionError(method)

    device = MagicMock(
        config={component.lower(): led_config},
        shelly={"mac": MAC},
        status={"switch:0": {"output": True}} if not meter else {},
        model=model,
        version="1.8.0",
        connected=True,
        initialize=AsyncMock(),
        shutdown=AsyncMock(),
        call_rpc=AsyncMock(side_effect=rpc),
    )
    device.name = "Test Plug"
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MAC, data={CONF_HOST: HOST})
    entry.add_to_hass(hass)
    with patch(
        "custom_components.shelly_led_control.api.RpcDevice.create", return_value=device
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    on_preset = registry.async_get_entity_id("light", DOMAIN, f"{MAC}_switch_on_color")
    off_preset = registry.async_get_entity_id(
        "light", DOMAIN, f"{MAC}_switch_off_color"
    )
    assert hass.states.get(on_preset).state == "on"
    assert (off_preset is None) == meter

    number = registry.async_get_entity_id("number", DOMAIN, f"{MAC}_normal_brightness")
    await hass.services.async_call(
        "number", "set_value", {"entity_id": number, "value": 50}, blocking=True
    )
    color_component = "pm1:0" if meter else "switch:0"
    assert led_config["leds"]["colors"][color_component]["on"]["brightness"] == 50
    device.call_rpc.assert_any_await(
        f"{component}.SetConfig", {"config": led_config}, timeout=RPC_TIMEOUT
    )
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_rpc_probe_only_continues_for_missing_method(hass, aioclient_mock):
    """Stop probing UI component names when the device reports a service error."""
    aioclient_mock.get(f"http://{HOST}/shelly", json={"gen": 2})
    device = MagicMock(
        config={},
        initialize=AsyncMock(),
        shutdown=AsyncMock(),
        call_rpc=AsyncMock(side_effect=[RpcCallError(404), RpcCallError(503)]),
    )
    client = ShellyLedClient(hass, HOST, None, None)
    with (
        patch(
            "custom_components.shelly_led_control.api.RpcDevice.create",
            return_value=device,
        ),
        pytest.raises(RpcCallError) as error,
    ):
        await client.async_connect()
    assert error.value.code == 503
    assert [call.args[0] for call in device.call_rpc.await_args_list] == [
        "PLUGS_UI.GetConfig",
        "PLUGUK_UI.GetConfig",
    ]
    device.shutdown.assert_awaited_once()


async def test_gen1_indicators_use_independent_authenticated_settings(
    hass, aioclient_mock
):
    """Expose the Gen1 LED flags and write only the targeted flag through HTTP."""
    aioclient_mock.get(
        f"http://{HOST}/shelly", json={"type": "SHPLG-S", "mac": MAC, "auth": True}
    )
    settings = {"led_status_disable": False, "led_power_disable": True}
    aioclient_mock.get(f"http://{HOST}/settings", json=settings)
    aioclient_mock.get(
        f"http://{HOST}/settings?led_power_disable=false",
        json={**settings, "led_power_disable": False},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={CONF_HOST: HOST, CONF_USERNAME: "admin", CONF_PASSWORD: "secret"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    network = registry.async_get_entity_id("light", DOMAIN, f"{MAC}_network_led")
    output = registry.async_get_entity_id("light", DOMAIN, f"{MAC}_output_led")
    assert hass.states.get(network).state == "on"
    assert hass.states.get(output).state == "off"
    assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 2

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": output}, blocking=True
    )
    discovery, *setting_calls = aioclient_mock.mock_calls
    auth_header = f"Basic {b64encode(b'admin:secret').decode()}"
    assert "Authorization" not in (discovery[3] or {})
    assert all(call[3]["Authorization"] == auth_header for call in setting_calls)
    writes = [call[1].query for call in setting_calls if call[1].query]
    assert [dict(query) for query in writes] == [{"led_power_disable": "false"}]
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_wave_setup_and_intensity(hass):
    """Expose Wave intensity as a light and restore the prior value after off."""
    zwave_entry = MockConfigEntry(domain="zwave_js")
    zwave_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=zwave_entry.entry_id,
        identifiers={("zwave_js", "1234-5")},
        name="Shelly Wave Plug S",
    )
    parameter = SimpleNamespace(value=35)
    writes = []

    async def set_parameter(call: ServiceCall) -> None:
        """Record the requested configuration value and update the reported cache."""
        writes.append(dict(call.data))
        parameter.value = call.data["value"]

    hass.services.async_register("zwave_js", "set_config_parameter", set_parameter)
    with (
        patch(
            "custom_components.shelly_led_control.config_flow.async_get_wave_led_parameter",
            return_value=parameter,
        ),
        patch(
            "custom_components.shelly_led_control.wave.async_get_wave_led_parameter",
            return_value=parameter,
        ),
    ):
        menu = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert menu["type"] == "menu"
        flow_id = menu["flow_id"]
        await hass.config_entries.flow.async_configure(
            flow_id, {"next_step_id": "wave"}
        )
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_DEVICE_ID: device.id}
        )
        await hass.async_block_till_done()

        assert result["type"] == "create_entry"
        unique_id = f"zwave_{device.id}_status_led"
        light = er.async_get(hass).async_get_entity_id("light", DOMAIN, unique_id)
        assert hass.states.get(light).attributes["brightness"] == 89
        for service in ("turn_off", "turn_on"):
            await hass.services.async_call(
                "light", service, {"entity_id": light}, blocking=True
            )

    assert writes == [
        {"device_id": device.id, "parameter": 105, "value": value} for value in (0, 35)
    ]
