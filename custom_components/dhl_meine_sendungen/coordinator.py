"""DataUpdateCoordinator für DHL Meine Sendungen."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .scraper import DHLAuthError, DHLScraper, DHLShipment

_LOGGER = logging.getLogger(__name__)


class DHLDataUpdateCoordinator(DataUpdateCoordinator[dict[str, DHLShipment]]):
    """Koordiniert die Datenabrufe von DHL."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        scan_interval: timedelta,
    ) -> None:
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=scan_interval,
        )
        self._scraper = DHLScraper(
            hass=hass,
            username=config_entry.data["username"],
            password=config_entry.data["password"],
        )
        self._logged_in = False

    async def _async_update_data(self) -> dict[str, DHLShipment]:
        """Aktualisiert Sendungsdaten von DHL."""
        try:
            if not self._logged_in:
                await self._scraper.async_login()
                self._logged_in = True

            shipments = await self._scraper.async_get_shipments()
            return {s.tracking_number: s for s in shipments}

        except DHLAuthError as err:
            self._logged_in = False
            raise ConfigEntryAuthFailed from err
        except Exception as err:
            self._logged_in = False
            raise UpdateFailed(f"DHL-Update fehlgeschlagen: {err}") from err

    async def async_shutdown(self) -> None:
        await self._scraper.async_shutdown()
