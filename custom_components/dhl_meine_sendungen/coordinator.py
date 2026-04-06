"""DataUpdateCoordinator für DHL Meine Sendungen."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .scraper import DHLScraper, DHLAuthError, DHLShipment

_LOGGER = logging.getLogger(__name__)


class DHLDataUpdateCoordinator(DataUpdateCoordinator[dict[str, DHLShipment]]):
    """Koordiniert die Datenabrufe von DHL."""

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
        scan_interval: timedelta,
    ) -> None:
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=scan_interval,
        )
        self._scraper = DHLScraper(username=username, password=password)
        self._logged_in = False

    async def _async_update_data(self) -> dict[str, DHLShipment]:
        """Aktualisiert Sendungsdaten von DHL."""
        try:
            if not self._logged_in:
                _LOGGER.debug("Nicht eingeloggt - führe Login durch...")
                await asyncio.wait_for(
                    self._scraper.async_login(),
                    timeout=60.0,
                )
                self._logged_in = True

            shipments = await asyncio.wait_for(
                self._scraper.async_get_shipments(),
                timeout=120.0,
            )

            return {s.tracking_number: s for s in shipments}

        except DHLAuthError as e:
            self._logged_in = False
            raise UpdateFailed(f"DHL Authentifizierungsfehler: {e}") from e
        except asyncio.TimeoutError as e:
            raise UpdateFailed("DHL-Abfrage hat Timeout überschritten.") from e
        except Exception as e:
            _LOGGER.error("Unerwarteter Fehler beim DHL-Update: %s", e)
            # Bei Fehler: nächstes Mal neu einloggen
            self._logged_in = False
            raise UpdateFailed(f"DHL-Update fehlgeschlagen: {e}") from e

    async def async_shutdown(self) -> None:
        """Fährt den Scraper herunter."""
        await self._scraper.async_shutdown()
