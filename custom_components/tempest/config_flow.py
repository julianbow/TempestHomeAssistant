"""Config flow for Tempest integration supporting both local and cloud modes with OAuth2 PKCE."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pyweatherflowudp.client import EVENT_DEVICE_DISCOVERED, WeatherFlowListener
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    LocalOAuth2ImplementationWithPkce,
)

from .const import (
    AUTHORIZE_URL,
    CLIENT_ID,
    DATA_SOURCE,
    DATA_SOURCE_OPTIONS,
    DOMAIN,
    ERROR_MSG_CANNOT_CONNECT,
    ERROR_MSG_NO_DEVICE_FOUND,
    TOKEN_URL,
)

_LOGGER = logging.getLogger(__name__)


async def _async_can_discover_devices() -> bool:
    """Attempt local device discovery via UDP broadcast."""
    fut: asyncio.Future[None] = asyncio.get_running_loop().create_future()

    @callback
    def _found(event_data: Any) -> None:
        _LOGGER.info("[DISCOVERY] Device found event fired: %s", event_data)
        if not fut.done():
            fut.set_result(None)

    try:
        async with WeatherFlowListener() as client, asyncio.timeout(10):
            client.on(EVENT_DEVICE_DISCOVERED, _found)
            await fut
    except TimeoutError:
        _LOGGER.warning("[DISCOVERY] No device discovered within timeout")
        return False
    except Exception:
        _LOGGER.exception("[DISCOVERY] Error during discovery")
        raise

    _LOGGER.info("[DISCOVERY] Device discovery successful")
    return True


class TempestPkceImplementation(LocalOAuth2ImplementationWithPkce):
    """PKCE implementation that normalizes provider token response for HA."""

    async def async_resolve_external_data(self, external_data: Any) -> dict[str, Any]:
        """Map the OAuth provider’s token payload into HA’s expected format."""
        raw = await super().async_resolve_external_data(external_data)
        return {
            "access_token": raw.get("access_token"),
            "refresh_token": raw.get("access_token"),
            "expires_in": int(raw.get("expires_in", 3600)),
            "token_type": raw.get("token_type", "Bearer"),
        }


class ConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle the configuration flow, allowing one local and one cloud entry."""

    VERSION = 1
    DOMAIN = DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return this flow’s logger."""
        return _LOGGER

    def _data_schema(self) -> vol.Schema:
        return vol.Schema(
            {vol.Required(DATA_SOURCE, default="local"): vol.In(DATA_SOURCE_OPTIONS)}
        )

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Let the user choose between Local or Cloud mode."""

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=self._data_schema(), errors={}
            )

        mode = user_input[DATA_SOURCE]
        # Prevent duplicate entries per mode immediately
        for entry in self._async_current_entries():
            if entry.data.get(DATA_SOURCE) == mode:
                return self.async_abort(reason="already_configured")

        # Register unique_id so HA’s registry also blocks duplicates
        await self.async_set_unique_id(mode)
        self._abort_if_unique_id_configured()

        if mode == "cloud":
            # Begin OAuth flow
            impl = TempestPkceImplementation(
                self.hass,
                self.DOMAIN,
                CLIENT_ID,
                AUTHORIZE_URL,
                TOKEN_URL,
            )
            self.flow_impl = impl
            return await self.async_step_auth()

        # Local mode: test discovery
        errors: dict[str, str] = {}
        try:
            found = await _async_can_discover_devices()
        except (TimeoutError, OSError):
            errors["base"] = ERROR_MSG_CANNOT_CONNECT
        else:
            if not found:
                errors["base"] = ERROR_MSG_NO_DEVICE_FOUND

        if errors:
            _LOGGER.warning("[STEP_USER] Local discovery errors: %s", errors)
            return self.async_show_form(
                step_id="user", data_schema=self._data_schema(), errors=errors
            )

        return self.async_create_entry(title="Tempest Station (Local)", data=user_input)

    async def async_oauth_create_entry(
        self, data: dict[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Create the config entry after OAuth2 completes."""
        # Prevent duplicate cloud entry at completion
        for entry in self._async_current_entries():
            if entry.data.get(DATA_SOURCE) == "cloud":
                return self.async_abort(reason="already_configured")

        await self.async_set_unique_id("cloud")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="Tempest Station (Cloud)", data=data)
