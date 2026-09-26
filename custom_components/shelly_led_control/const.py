"""Constants for Shelly LED Control."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "shelly_led_control"
DEFAULT_ENABLED_LED_MODE: Final = "switch"
LED_MODE_OFF: Final = "off"
RPC_TIMEOUT: Final = 10.0
UPDATE_INTERVAL: Final = timedelta(minutes=5)
