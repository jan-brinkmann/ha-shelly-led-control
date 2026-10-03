[Deutsche Dokumentation](README.de.md)

# Shelly LED Control

**Shelly LED Control** lets you control the status LED of your Shelly Plus Plug S directly in Home Assistant. Adjust its colors, brightness and night mode locally on your home network, without a cloud connection. The integration works alongside Home Assistant's official Shelly integration.

## Features

- Turn the status LED on and off from dashboards, scenes and automations.
- Choose an LED display based on power consumption or the plug's on/off state.
- Set separate colors and brightness for when the plug is on or off.
- Schedule night mode to dim the LED or turn it off at night.
- View the current LED brightness and night-mode status, with brightness history in Home Assistant.

![Shelly LED Control banner](docs/banner.png)

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Downloads](https://img.shields.io/github/downloads/jan-brinkmann/ha-shelly-led-control/total?label=downloads)](https://github.com/jan-brinkmann/ha-shelly-led-control/releases)
[![Release](https://img.shields.io/github/v/release/jan-brinkmann/ha-shelly-led-control?label=release)](https://github.com/jan-brinkmann/ha-shelly-led-control/releases/latest)

## Supported devices

The supported model is **Shelly Plus Plug S** (`SNPL-00112EU`). Other Shelly Wall Plugs may work, but are not officially supported. Your Shelly must be reachable from Home Assistant on the local network.

## Installation

### With HACS (recommended)

1. Install [HACS](https://hacs.xyz) if needed.
2. Open **HACS → Custom repositories** in the three-dot menu. Add `https://github.com/jan-brinkmann/ha-shelly-led-control` as an **Integration**.
3. Download **Shelly LED Control** and restart Home Assistant.

### Manual installation

1. Copy the `custom_components/shelly_led_control` folder into your Home Assistant configuration's `custom_components` folder.
2. Restart Home Assistant.

## Setup

1. Open **Settings → Devices & services → Add integration** and select **Shelly LED Control**.
2. Enter your Shelly's hostname or IP address.
3. Keep the default username `admin`. Enter the device password if login protection is enabled; otherwise leave it empty.

Repeat these steps for each Shelly you want to add. Devices are added manually.

## Usage

Open the device under **Settings → Devices & services → Shelly LED Control**. Its controls are also available in dashboards, scenes and automations.

| Control | What it does |
| --- | --- |
| **Status LED** | Turns LED indication on or off. |
| **LED indication mode** | Selects **Power consumption** or **Switch state**. Selecting a mode enables LED indication. |
| **LED color when relay is on / off** | Sets each state's color and brightness in **Switch state** mode. These controls do not switch the plug itself. |
| **Normal brightness** | Sets brightness outside night mode from 0 to 100%. In **Switch state** mode, it sets brightness for the plug's current on/off state. |
| **Use night mode** | Enables the night-mode schedule. |
| **Night mode start / end** and **Night mode brightness** | Set the schedule and brightness. Use 0% to turn the LED off during night mode. |
| **Night mode active** | Shows whether the scheduled night mode is currently active. |
| **Status LED brightness** | Shows the current brightness in percent, including night mode, and provides a history. |

In **Power consumption** mode, Shelly chooses the color automatically; custom colors are available in **Switch state** mode. When the plug is off, power-consumption indication is off too.

Night mode follows the Shelly's local time and can run across midnight. **Status LED brightness** is calculated from the device settings and state.

If you also use the official Shelly integration, Home Assistant shows a separate device entry for the LED controls. This is normal.

## Help and updates

- **Cannot connect?** Check that the Shelly is online and its web interface is reachable from the Home Assistant network.
- **Login failed?** Check the device password and use Home Assistant's reauthentication prompt if it appears.
- **Night-mode status is unknown?** Check that the Shelly's clock is set correctly.
- **Changed settings in the Shelly web interface?** They update automatically in Home Assistant; allow up to five minutes if an update is delayed.

Update through HACS and restart Home Assistant when requested. For manual updates, replace the integration folder and restart Home Assistant. Your existing configuration is kept.

For implementation details, see [Technical decisions](docs/architecture.md).

## License

Released under the [MIT License](LICENSE).
