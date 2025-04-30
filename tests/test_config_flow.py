"""Tests for config_flow.py of the Tempest integration (homeassistant.components.tempest)."""

from types import SimpleNamespace

import pytest

from homeassistant.components.tempest.config_flow import (
    ConfigFlow,
    TempestPkceImplementation,
)
from homeassistant.core import HomeAssistant

DATA_SOURCE = "data_source"


@pytest.mark.asyncio
async def test_show_form(hass: HomeAssistant) -> None:
    """Initial step shows a form."""
    flow = ConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user(None)
    assert result["type"] == "form"
    assert "data_schema" in result


@pytest.mark.asyncio
async def test_local_flow_success(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant
) -> None:
    """Local branch creates entry when discovery succeeds."""

    # Patch discovery to always succeed
    async def fake_discover():
        return True

    monkeypatch.setattr(
        "homeassistant.components.tempest.config_flow._async_can_discover_devices",
        fake_discover,
    )
    flow = ConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user({DATA_SOURCE: "local"})
    assert result["type"] == "create_entry"
    assert result["title"] == "Tempest Station (Local)"


@pytest.mark.asyncio
async def test_local_flow_failure(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant
) -> None:
    """Local branch returns form with error when discovery fails."""

    async def fake_discover():
        return False

    monkeypatch.setattr(
        "homeassistant.components.tempest.config_flow._async_can_discover_devices",
        fake_discover,
    )
    flow = ConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user({DATA_SOURCE: "local"})
    assert result["type"] == "form"
    # error base can be no_device_found or cannot_connect
    assert result["errors"]["base"] in ("cannot_connect", "no_device_found")


@pytest.mark.asyncio
async def test_cloud_flow(monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant) -> None:
    """Cloud branch registers PKCE impl and goes to auth step."""
    flow = ConfigFlow()
    flow.hass = hass
    # No existing entries
    monkeypatch.setattr(flow, "_async_current_entries", list)

    # Patch async_step_auth to avoid redirect_uri error
    async def fake_auth():
        return {"step_id": "auth"}

    monkeypatch.setattr(flow, "async_step_auth", fake_auth)

    result = await flow.async_step_user({DATA_SOURCE: "cloud"})
    assert result["step_id"] == "auth"
    assert isinstance(flow.flow_impl, TempestPkceImplementation)


@pytest.mark.asyncio
async def test_duplicate_prevention(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant
) -> None:
    """Duplicate entries per mode are aborted."""
    # Prevent duplicate local
    existing_local = [SimpleNamespace(data={DATA_SOURCE: "local"})]
    flow = ConfigFlow()
    flow.hass = hass
    monkeypatch.setattr(flow, "_async_current_entries", lambda: existing_local)
    result = await flow.async_step_user({DATA_SOURCE: "local"})
    assert result.get("reason") == "single_instance_allowed"

    # Prevent duplicate cloud
    existing_cloud = [SimpleNamespace(data={DATA_SOURCE: "cloud"})]
    flow2 = ConfigFlow()
    flow2.hass = hass
    monkeypatch.setattr(flow2, "_async_current_entries", lambda: existing_cloud)
    # Also patch async_step_auth
    monkeypatch.setattr(flow2, "async_step_auth", lambda: None)
    result2 = await flow2.async_step_user({DATA_SOURCE: "cloud"})
    assert result2.get("reason") == "single_instance_allowed"
