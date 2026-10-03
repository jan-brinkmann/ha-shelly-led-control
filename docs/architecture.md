# Technical decisions

## Local RPC and state

The integration uses the asynchronous `aioshelly` library that also powers Home Assistant's official Shelly integration. It opens a local Gen2 RPC WebSocket, supports Shelly's SHA-256 digest authentication, and receives device notifications without changing the device's existing outbound-WebSocket settings.

The integration reads `PLUGS_UI.GetConfig`. `leds.mode: off` maps to a Home Assistant light state of off. An enabled night mode with brightness `0` also maps to off while the Shelly-local time is inside its configured window; every other supported configuration maps to on. `PLUGS_UI.GetStatus` has no independent status values, so this is a configuration-state mapping rather than a direct measurement of emitted light. The coordinator reads `Sys.GetStatus.time`, using `unixtime` for its seconds when available, and schedules a refresh at each zero-brightness night-mode boundary. `NotifyEvent` events reporting a `PLUGS_UI` `config_changed` request an immediate refresh. A five-minute refresh is retained as a fallback for missed events and direct device changes.

For every service call, the integration reads the full `PLUGS_UI` configuration. It sends `PLUGS_UI.SetConfig` with the unchanged configuration and only a modified `leds.mode` or selected `leds.night_mode` fields. Off always writes `off`. On restores the last non-off mode observed during the current runtime; if the device starts in off mode after a Home Assistant restart, the documented stable fallback is `switch`. The night-mode switch changes only `enable`; the time entities change only the relevant `active_between` value. This keeps existing colors, brightness, and controls values.

`leds.night_mode.active_between` is represented by two configuration time entities using Shelly's local `HH:MM` format. Night-mode brightness is intentionally read and preserved but not exposed as an entity.

## Identity and coexistence

The config flow gets the MAC address from the Shelly API and formats it using Home Assistant's MAC helper. It is the config entry's unique ID and the light's stable unique-ID suffix; hostnames and IP addresses are not used as identity.

The official Shelly integration also associates its device with the Shelly MAC address. However, current Home Assistant device-registry rules scope identifiers and network connections to the config entry that owns them. A physical device supported by more than one integration has one device entry per owning config entry; another integration cannot safely add an entity to the existing official Shelly device entry. This integration therefore creates its own device-registry entry with its own domain identifier and the same normalized network MAC. This is intentional, avoids registry collisions, and leaves the official Shelly integration untouched.

## Scope deliberately deferred

Version 1.0.0 exposes one on/off light, a night-mode switch, and start/end time entities. RGB, brightness, explicit mode selection, power indication, discovery and support for additional models are planned separately and are not implemented here.
