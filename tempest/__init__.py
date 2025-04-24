"""Unified init for Tempest Test integration supporting both local and cloud modes."""

from __future__ import annotations

from pyweatherflowudp.client import EVENT_DEVICE_DISCOVERED, WeatherFlowListener
from pyweatherflowudp.device import EVENT_LOAD_COMPLETE, WeatherFlowDevice
from pyweatherflowudp.errors import ListenerError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN, LOGGER, format_dispatch_call
from .coordinator import WeatherFlowCloudDataUpdateCoordinator

# This is what tests will patch — default is sensor + weather
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Tempest Test integration from a config entry."""
    # Cloud mode if we have a token
    if "token" in entry.data:
        if WeatherFlowCloudDataUpdateCoordinator is None:
            LOGGER.error("Cloud coordinator not available")
            return False
        coordinator = WeatherFlowCloudDataUpdateCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
        # Forward to whichever platforms are in PLATFORMS
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True

    # Local (UDP) mode
    client = WeatherFlowListener()
    entry.runtime_data = client

    @callback
    def _async_device_discovered(device: WeatherFlowDevice) -> None:
        LOGGER.debug("Local mode: Found device %s", device)

        @callback
        def _async_add_device(dev: WeatherFlowDevice) -> None:
            async_at_started(
                hass,
                callback(
                    lambda _: async_dispatcher_send(
                        hass, format_dispatch_call(entry), dev
                    )
                ),
            )

        entry.async_on_unload(
            device.on(EVENT_LOAD_COMPLETE, lambda _: _async_add_device(device))
        )

    entry.async_on_unload(client.on(EVENT_DEVICE_DISCOVERED, _async_device_discovered))

    try:
        await client.start_listening()
    except ListenerError as ex:
        raise ConfigEntryNotReady from ex

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client
    # Forward to the same PLATFORMS list, so tests can override it
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(
        hass.bus.async_listen(
            EVENT_HOMEASSISTANT_STOP,
            lambda event: client.stop_listening(),
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload exactly the same platforms we loaded
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Clean up stored data
        integration_data = hass.data.get(DOMAIN, {})
        client_or_coord = integration_data.pop(entry.entry_id, None)
        # If local, stop the listener
        if client_or_coord and "token" not in entry.data:
            await client_or_coord.stop_listening()
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device.

    For local mode, verify no discovered devices match this device entry.
    For cloud mode, always allow removal.
    """
    if "token" in config_entry.data:
        return True

    client: WeatherFlowListener = hass.data[DOMAIN][config_entry.entry_id]
    # Return False if any device.serial_number still matches an identifier
    return not any(
        identifier[0] == DOMAIN and device.serial_number == identifier[1]
        for identifier in device_entry.identifiers
        for device in client.devices
    )
