[Deutsche Dokumentation](README.de.md)

# Shelly LED Control

![Shelly LED Control banner](docs/banner.png)

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Downloads](https://img.shields.io/github/downloads/jan-brinkmann/ha-shelly-led-control/total?label=downloads)](https://github.com/jan-brinkmann/ha-shelly-led-control/releases)
[![Release](https://img.shields.io/github/v/release/jan-brinkmann/ha-shelly-led-control?label=release)](https://github.com/jan-brinkmann/ha-shelly-led-control/releases/latest)
![GitHub commits since latest release](https://img.shields.io/github/commits-since/jan-brinkmann/ha-shelly-led-control/latest)
[![Commit activity](https://img.shields.io/github/commit-activity/m/jan-brinkmann/ha-shelly-led-control)](https://github.com/jan-brinkmann/ha-shelly-led-control/commits/main)
[![Validate](https://github.com/jan-brinkmann/ha-shelly-led-control/actions/workflows/validate.yml/badge.svg)](https://github.com/jan-brinkmann/ha-shelly-led-control/actions/workflows/validate.yml)

`Shelly LED Control` is a local Home Assistant custom integration for configuring the status LED of a Shelly Plus Plug S. It provides on/off control, indication-mode selection, relay-state colors and brightness settings. It is designed to run beside Home Assistant's official Shelly integration; it does not replace it.

## Supported device

- Shelly Plus Plug S (`SNPL-00112EU`) is the primary supported device.
- Other Shelly Wall Plugs may work when their local Gen2+ RPC API provides the `PLUGS_UI` component with `PLUGS_UI.GetConfig` and `PLUGS_UI.SetConfig`.

## Current features

- One `light` entity named **Status LED** for each configured Shelly.
- `light.turn_on` enables LED indication and `light.turn_off` disables it.
- An **LED indication mode** configuration selector with **Power consumption** and **Switch state**.
- Two RGB configuration lights, **LED color when relay is on** and **LED color when relay is off**, for independent colors and normal brightness in **Switch state** mode.
- `mode: off`, or an effective brightness of zero, is represented as off; the state uses the Shelly's local clock and updates at night-mode boundaries.
- In **Power consumption** mode, a relay that is off gives 0% effective brightness and an off **Status LED**, including during night mode; its saved normal brightness stays unchanged.
- A **Use night mode** configuration switch plus **Night mode start** and **Night mode end** time entities.
- A read-only **Night mode active** binary sensor that is on when night mode is enabled and the Shelly's local time is inside its configured window, independent of brightness.
- A read-only **Status LED brightness** sensor for the current effective brightness from 0 to 100%, including night mode, with Home Assistant history and long-term statistics.
- A **Night mode brightness** configuration number from 0 to 100% in 1% steps.
- A **Normal brightness** configuration number from 0 to 100% in 1% steps for the current LED mode and relay state outside night mode.
- The night-mode time window is written as Shelly's local `HH:MM` start and end values without changing its configured brightness.
- Uses local asynchronous Shelly RPC, digest authentication when enabled, push events and a five-minute fallback refresh.
- Supports multiple devices with MAC-address-based unique IDs.

## Installation

### Preferred: HACS

1. Install [HACS](https://hacs.xyz) if necessary.
2. Open **HACS**, select **Custom repositories** in the three-dot menu, and add `https://github.com/jan-brinkmann/ha-shelly-led-control` as an **Integration**.
3. Download **Shelly LED Control**, restart Home Assistant, then add it in **Settings → Devices & services → Add integration**.

### Manual installation

1. Copy `custom_components/shelly_led_control` to `<configuration_directory>/custom_components/shelly_led_control`.
2. Restart Home Assistant and add **Shelly LED Control** in **Settings → Devices & services → Add integration**.

## Configuration

Enter the Shelly hostname or IP address. The integration verifies the local connection and checks for `PLUGS_UI` before creating an entry. Shelly Gen2 devices normally use `admin`; leave the password empty when authentication is disabled, otherwise enter the device password. Home Assistant stores credentials in the config entry and never writes them to logs.

Configure every physical Shelly separately. The MAC address received from the Shelly API is the stable config-entry and entity identity, so a DHCP address change does not create a new entity.

## Usage

Use **Status LED** like any on/off light in dashboards, automations, scenes or with `light.turn_on` and `light.turn_off`.

- **Off** writes `PLUGS_UI.leds.mode: off`.
- **On** restores the last non-off mode seen while the integration is running. After a Home Assistant restart while the device is off, it uses `switch` as the stable enabled mode.

Use **LED indication mode** in the device's configuration area to select **Power consumption** (`power`) or **Switch state** (`switch`). Selecting either mode enables LED indication. Use the existing **Status LED** light to turn indication completely off. While indication is off, the selector shows **Unknown**, since neither enabled mode is active; you can still select a mode to enable it again. External changes in the Shelly web UI update the selection.

In **Switch state** mode, open **LED color when relay is on** and **LED color when relay is off** to choose each state's color using Home Assistant's color picker. These are configuration presets: editing either one does not switch the plug's relay. Their brightness sliders adjust each state's normal brightness independently, including the state that is not currently active. Changing only the color preserves its brightness and all night-mode settings. The preset light's on/off state reflects its configured normal brightness, independently of relay output and night-mode activity. Turning a preset off sets only its brightness to 0%; turning it on without a color or brightness restores a zero-brightness preset to 100%. Turning it on with only a color preserves even zero brightness. Both presets are unavailable outside **Switch state** mode. In **Power consumption** mode, Shelly determines the color automatically from consumption; normal brightness remains configurable. See the [Shelly configuration schema](https://shelly-api-docs.shelly.cloud/gen2/Devices/Gen2/ShellyPlusPlugS/).

The complete current `PLUGS_UI` configuration is read before every write. Only the requested `leds.mode`, RGB/brightness field in `leds.colors`, or `leds.night_mode` field changes; all other settings, including the other relay state's color and brightness and the plug's controls, are preserved. Successful service calls immediately refresh all entities from the device, including consecutive changes.

Use **Normal brightness** in the device's configuration area to set the brightness outside night mode from 0 to 100%. In `power` mode, it changes the power indication brightness. In `switch` mode, it changes only the brightness for the current relay output (on or off); the other state's brightness is preserved. The setting follows changes to the LED mode and relay output. It always shows the normal setting, including while night mode is active, so you can prepare the brightness used after night mode ends. Night-mode brightness and its schedule remain unchanged. At 0%, the LED is off outside night mode. The setting is unavailable while LED indication is disabled (`mode: off`) or the mode is unsupported. Missing brightness or unknown relay output gives **Unknown**. You can also use `number.set_value` in automations.

Use the **Use night mode** switch in the device's configuration area to choose whether the Shelly night mode is used. An enabled switch means the schedule is enabled; it does not indicate that night mode is currently active. Set **Night mode start** and **Night mode end** to define its local time window. Set **Night mode brightness** to the desired LED brightness from 0 to 100%; 0% turns the LED off during the active night-mode window. The value can also be changed through `number.set_value` in automations. Changing brightness preserves the enabled state and time window, and changing the switch or either time preserves brightness.

**Night mode active** is a read-only status: **On** means night mode is enabled and the Shelly's local clock is inside its time window; otherwise it is **Off**. The status applies at any night-mode brightness, including when the LED indication mode is off, and updates at the window's start and end. The start time is included and the end time excluded; windows can cross midnight. If night mode is enabled but the Shelly has not synchronized its clock, the status is **Unknown**. The renamed switch keeps its existing entity ID for existing installations.

**Status LED brightness** shows the current effective brightness in percent. Disabled LED indication is 0%. In **Power consumption** mode, a relay that is off also gives 0%, including during night mode; the **Normal brightness** setting still shows its saved value for when the relay turns on. With the relay on, 0 W does not imply 0% brightness: Shelly represents zero load by a green LED. Otherwise active night mode uses its configured brightness. Outside night mode, the sensor uses the `power` mode brightness or, in `switch` mode, the brightness for the current relay output. It updates on configuration and relay changes and at night-mode boundaries. The value is calculated from settings and device state reported by Shelly; it does not measure emitted light. See the [Shelly LED behavior](https://kb.shelly.cloud/knowledge-base/shelly-plus-plug-s-v2) and [Shelly API](https://shelly-api-docs.shelly.cloud/gen2/Devices/Gen2/ShellyPlusPlugS/).

Home Assistant records the sensor in history unless it is excluded in the Recorder configuration. The `measurement` state class also enables long-term statistics. Missing required brightness or relay data, or an unsynchronized Shelly clock while night mode is enabled, produces **Unknown**. A power-mode relay known to be off remains 0% even without a synchronized clock; unknown relay output cannot produce a positive power-mode brightness, although a known zero brightness still gives 0%. A disconnected device produces **Unavailable**.

## Current limitations

The integration supports LED on/off, selection of power- or switch-based indication, separate switch-state RGB colors and brightness, displaying and recording effective brightness, adjusting normal brightness, plus enabling, disabling, scheduling and adjusting the brightness of night mode. Custom power-to-color mappings and automatic discovery are not implemented. `PLUGS_UI` has no independent live status, so the entities derive LED state from settings and device state; color configuration lights represent presets rather than measured light output.

## Compatibility

The integration uses a separate config entry and MAC-based device-registry connection. Current Home Assistant device-registry rules scope device identity to the owning config entry, so an entity from this custom integration cannot safely be inserted into the device entry owned by the official Shelly integration. Home Assistant therefore shows a separate integration-owned device entry for the same physical plug; the official Shelly integration continues to manage its existing entities without collision. See [Architecture](docs/architecture.md).

## Troubleshooting

- Confirm the device is reachable from Home Assistant and its local RPC API is enabled.
- Confirm the device provides `PLUGS_UI` and uses supported Plus Plug S firmware.
- If authentication is enabled, use the integration's reauthentication flow and enter current `admin` credentials.
- Edits in the device web UI, including RGB-only changes, refresh the entities through `plugs_ui` `config_changed` events or changes to `sys.cfg_rev` in status notifications. Component-name matching is case-insensitive. If notifications are missed, the five-minute fallback refresh still reads the current settings.
- If startup fails with `No module named 'aioshelly.json'`, update all integration files, including `manifest.json`, then fully restart Home Assistant Core. This integration uses the `aioshelly` version managed by Home Assistant's built-in Shelly integration; it does not install a separate version. A reload alone does not clear Python modules already loaded during startup.

## Updating

Update through HACS and restart Home Assistant when requested. For manual installations, replace only `custom_components/shelly_led_control` and restart Home Assistant. Existing config entries remain intact.

## Planned features

Future versions may add automatic discovery and additional Shelly models. These features are not implemented yet.

## License

This project is released under the [MIT License](LICENSE).
