"""Tests for __init__.py of the Tempest integration (homeassistant.components.tempest)."""

from types import SimpleNamespace

import pytest

import homeassistant.components.tempest as integration
from homeassistant.components.tempest.const import DOMAIN
from homeassistant.core import HomeAssistant


class DummyCoordinator:
    """A dummy cloud coordinator for testing purposes.

    This class simulates a cloud coordinator that interacts with the Home Assistant
    instance and a configuration entry without performing actual cloud operations.
    """

    def __init__(self, hass: HomeAssistant, entry: SimpleNamespace) -> None:
        """Initialize a dummy cloud coordinator with HA instance and entry."""
        self.hass = hass
        self.entry = entry

    async def async_config_entry_first_refresh(self) -> None:
        """Simulate the first refresh of cloud data with no action."""
        return


class DummyListener:
    """A dummy local UDP listener for testing purposes.

    This class simulates a local listener that can subscribe to events
    and manage devices without performing actual network operations.
    """

    def __init__(self) -> None:
        """Initialize a dummy local UDP listener with no devices."""
        self.devices = []

    def on(self, event: str, callback) -> None:
        """Simulate subscribing to a listener event."""
        return lambda: None

    async def start_listening(self) -> None:
        """Simulate starting UDP listening without error."""
        return

    async def stop_listening(self) -> None:
        """Simulate stopping UDP listening without error."""
        return


@pytest.fixture(autouse=True)
def patch_forward_and_unload(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant
) -> None:
    """Patch HA config_entries methods for forwarding and unloading platforms."""

    async def fake_forward(entry, platforms) -> bool:
        """Fake async_forward_entry_setups always returns True."""
        return True

    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", fake_forward)

    async def fake_unload(entry, platforms) -> bool:
        """Fake async_unload_platforms always returns True."""
        return True

    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", fake_unload)


@pytest.mark.asyncio
async def test_async_setup_entry_cloud(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant
) -> None:
    """Test that async_setup_entry correctly sets up cloud mode and coordinator."""
    entry = SimpleNamespace(data={"token": {"access_token": "abc"}}, entry_id="c1")
    # Stub async_on_unload in case called
    entry.async_on_unload = lambda callback: None
    monkeypatch.setattr(
        integration, "WeatherFlowCloudDataUpdateCoordinator", DummyCoordinator
    )

    result = await integration.async_setup_entry(hass, entry)
    assert result is True
    assert isinstance(hass.data[DOMAIN]["c1"], DummyCoordinator)


@pytest.mark.asyncio
async def test_async_setup_entry_cloud_no_coord(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant
) -> None:
    """Test that async_setup_entry returns False if cloud coordinator is unavailable."""
    entry = SimpleNamespace(data={"token": {}}, entry_id="c2")
    # Stub async_on_unload in case called
    entry.async_on_unload = lambda callback: None
    monkeypatch.setattr(integration, "WeatherFlowCloudDataUpdateCoordinator", None)

    result = await integration.async_setup_entry(hass, entry)
    assert result is False


@pytest.mark.asyncio
async def test_async_setup_entry_local(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant
) -> None:
    """Test that async_setup_entry correctly sets up local mode and listener."""
    entry = SimpleNamespace(data={}, entry_id="l1")
    # Provide async_on_unload to prevent attribute errors
    entry.async_on_unload = lambda callback: None
    monkeypatch.setattr(integration, "WeatherFlowListener", DummyListener)

    result = await integration.async_setup_entry(hass, entry)
    assert result is True
    assert isinstance(hass.data[DOMAIN]["l1"], DummyListener)


@pytest.mark.asyncio
async def test_async_unload_entry_cloud(hass: HomeAssistant) -> None:
    """Test that async_unload_entry for cloud mode removes entry data."""
    entry = SimpleNamespace(data={"token": {}}, entry_id="c1")
    # Stub async_on_unload to allow listener cleanup
    entry.async_on_unload = lambda callback: None
    hass.data.setdefault(DOMAIN, {})["c1"] = "to_remove"

    result = await integration.async_unload_entry(hass, entry)
    assert result is True
    assert "c1" not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_async_remove_config_entry_device(hass: HomeAssistant) -> None:
    """Test removal behavior of config entry devices for both cloud and local."""
    # Cloud mode always returns True
    entry = SimpleNamespace(data={"token": {}}, entry_id="cX")
    device = SimpleNamespace(identifiers=[])
    assert (
        await integration.async_remove_config_entry_device(hass, entry, device) is True
    )

    # Local mode: matching device should return False
    listener = DummyListener()
    listener.devices = [SimpleNamespace(serial_number="abc")]
    hass.data.setdefault(DOMAIN, {})["l1"] = listener
    entry_local = SimpleNamespace(data={}, entry_id="l1")
    device_match = SimpleNamespace(identifiers=[(DOMAIN, "abc")])
    assert (
        await integration.async_remove_config_entry_device(
            hass, entry_local, device_match
        )
        is False
    )
    # Non-matching device should return True
    device_no_match = SimpleNamespace(identifiers=[(DOMAIN, "xyz")])
    assert (
        await integration.async_remove_config_entry_device(
            hass, entry_local, device_no_match
        )
        is True
    )
