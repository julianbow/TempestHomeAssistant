"""Constants."""

import logging

from homeassistant.config_entries import ConfigEntry

CONF_ACCESS_TOKEN = "access_token"
DOMAIN = "tempest"

AUTHORIZE_URL = "https://smartweather.weatherflow.com/authorize.html"
TOKEN_URL = "https://swd.weatherflow.com/id/oauth2/token"

CLIENT_ID = "1f59ad93-2c35-40b1-b984-ace096dbe624"

MANUFACTURER = "Tempest"

DATA_SOURCE = "data_source"

DATA_SOURCE_OPTIONS = {"local": "Local", "cloud": "Cloud"}

LOGGER = logging.getLogger(__package__)


def format_dispatch_call(config_entry: ConfigEntry) -> str:
    """Construct a dispatch call from a ConfigEntry."""
    return f"{config_entry.domain}_{config_entry.entry_id}_add"


ERROR_MSG_ADDRESS_IN_USE = "address_in_use"
ERROR_MSG_CANNOT_CONNECT = "cannot_connect"
ERROR_MSG_NO_DEVICE_FOUND = "no_devices_found"

ATTR_ATTRIBUTION = "Weather data delivered by Tempest REST Api"

STATE_MAP = {
    "clear-day": "sunny",
    "clear-night": "clear-night",
    "cloudy": "cloudy",
    "foggy": "fog",
    "partly-cloudy-day": "partlycloudy",
    "partly-cloudy-night": "partlycloudy",
    "possibly-rainy-day": "rainy",
    "possibly-rainy-night": "rainy",
    "possibly-sleet-day": "snowy-rainy",
    "possibly-sleet-night": "snowy-rainy",
    "possibly-snow-day": "snowy",
    "possibly-snow-night": "snowy",
    "possibly-thunderstorm-day": "lightning-rainy",
    "possibly-thunderstorm-night": "lightning-rainy",
    "rainy": "rainy",
    "sleet": "snowy-rainy",
    "snow": "snowy",
    "thunderstorm": "lightning",
    "windy": "windy",
}
