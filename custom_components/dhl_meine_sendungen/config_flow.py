"""Config Flow für DHL Meine Sendungen."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class DHLConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow Handler für DHL Meine Sendungen."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Erster Schritt: Zugangsdaten eingeben."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            # Playwright-Verfügbarkeit prüfen BEVOR wir den Scraper starten
            try:
                import playwright  # noqa: F401
            except ImportError:
                errors["base"] = "playwright_missing"
                return self.async_show_form(
                    step_id="user",
                    data_schema=STEP_USER_DATA_SCHEMA,
                    errors=errors,
                )

            # Login testen
            try:
                # Lazy import – scraper.py wird erst hier geladen
                from .scraper import DHLScraper, DHLAuthError

                scraper = DHLScraper(username=username, password=password)
                try:
                    await asyncio.wait_for(
                        scraper.async_login(),
                        timeout=60.0,
                    )
                finally:
                    await scraper.async_shutdown()

                return self.async_create_entry(
                    title=f"DHL – {username}",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                )

            except ImportError as exc:
                _LOGGER.error("Import-Fehler im Scraper: %s", exc)
                errors["base"] = "playwright_missing"
            except asyncio.TimeoutError:
                errors["base"] = "timeout"
            except Exception as exc:
                exc_lower = str(exc).lower()
                _LOGGER.error("Fehler beim DHL-Login-Test (%s): %s", type(exc).__name__, exc)
                if any(w in exc_lower for w in ("auth", "login", "password", "credential", "invalid")):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> DHLOptionsFlow:
        return DHLOptionsFlow(config_entry)


class DHLOptionsFlow(config_entries.OptionsFlow):
    """Options Flow für Update-Intervall."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=1440)),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
