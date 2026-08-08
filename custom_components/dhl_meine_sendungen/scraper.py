"""DHL Sendungsverfolgung via HTTP/API – kein Playwright, läuft auf HA OS."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)
REQUEST_TIMEOUT = 30

# DHL Endpunkte
DHL_LOGIN_URL = "https://www.dhl.de/int-erkennen/rest/logininfo"
DHL_TOKEN_URL = "https://www.dhl.de/int-erkennen/rest/auth/login"
DHL_SENDUNGEN_URL = "https://www.dhl.de/int-erkennen/rest/data"
DHL_TRACKING_URL = "https://www.dhl.de/int-erkennen/rest/data"

# User-Agent der einen echten Browser simuliert
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Referer": "https://www.dhl.de/",
    "Origin": "https://www.dhl.de",
}


@dataclass
class DHLShipmentEvent:
    timestamp: str
    location: str
    description: str

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "location": self.location,
            "description": self.description,
        }


@dataclass
class DHLLiveStatus:
    stops_remaining: int | None = None
    estimated_delivery_start: str | None = None
    estimated_delivery_end: str | None = None
    current_location: str | None = None
    driver_name: str | None = None
    map_url: str | None = None

    def to_dict(self) -> dict:
        return {
            "stops_remaining": self.stops_remaining,
            "estimated_delivery_start": self.estimated_delivery_start,
            "estimated_delivery_end": self.estimated_delivery_end,
            "current_location": self.current_location,
            "driver_name": self.driver_name,
            "map_url": self.map_url,
        }


@dataclass
class DHLShipment:
    tracking_number: str
    status: str
    status_text: str
    description: str
    sender: str | None = None
    recipient: str | None = None
    estimated_delivery: str | None = None
    delivery_date: str | None = None
    weight: str | None = None
    product: str | None = None
    events: list[DHLShipmentEvent] = field(default_factory=list)
    live_status: DHLLiveStatus | None = None

    def to_dict(self) -> dict:
        return {
            "tracking_number": self.tracking_number,
            "status": self.status,
            "status_text": self.status_text,
            "description": self.description,
            "sender": self.sender,
            "recipient": self.recipient,
            "estimated_delivery": self.estimated_delivery,
            "delivery_date": self.delivery_date,
            "weight": self.weight,
            "product": self.product,
            "events": [e.to_dict() for e in self.events],
            "live_status": self.live_status.to_dict() if self.live_status else None,
        }


class DHLAuthError(Exception):
    pass


class DHLScraper:
    """
    DHL Sendungsverfolgung via aiohttp (kein Playwright, kein pip install nötig).
    Nutzt die interne DHL REST API die auch der Browser verwendet.
    """

    def __init__(self, hass, username: str, password: str) -> None:
        self._hass = hass
        self._username = username
        self._password = password
        self._session = None
        self._auth_token: str | None = None
        self._cookies: dict = {}

    def _get_session(self):
        if self._session is None:
            self._session = async_get_clientsession(self._hass)
        return self._session

    async def async_login(self) -> bool:
        """Login bei DHL via REST API."""
        session = self._get_session()

        try:
            # Schritt 1: CSRF/Session-Token holen
            async with session.get(
                "https://www.dhl.de/de/privatkunden.html",
                headers=HEADERS,
                allow_redirects=True,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                # Cookies sammeln
                for cookie_name, cookie in resp.cookies.items():
                    self._cookies[cookie_name] = cookie.value
                _LOGGER.debug("DHL Startseite aufgerufen, Status: %s", resp.status)

            # Schritt 2: Login-Endpunkt aufrufen
            login_headers = {
                **HEADERS,
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            }

            login_payload = {
                "authInfo": {
                    "username": self._username,
                    "password": self._password,
                    "rememberMe": False,
                }
            }

            # Versuche verschiedene Login-Endpunkte
            login_endpoints = [
                "https://www.dhl.de/int-erkennen/rest/auth/login",
                "https://www.dhl.de/int-webapp/spa/assets/auth/login",
            ]

            logged_in = False
            for endpoint in login_endpoints:
                try:
                    async with session.post(
                        endpoint,
                        json=login_payload,
                        headers=login_headers,
                        cookies=self._cookies,
                        allow_redirects=True,
                        timeout=REQUEST_TIMEOUT,
                    ) as resp:
                        _LOGGER.debug("Login-Versuch auf %s: Status %s", endpoint, resp.status)
                        if resp.status in (200, 201):
                            try:
                                data = await resp.json(content_type=None)
                                # Token aus Response extrahieren
                                self._auth_token = (
                                    data.get("token")
                                    or data.get("access_token")
                                    or data.get("authToken")
                                )
                                # Neue Cookies speichern
                                for cn, cv in resp.cookies.items():
                                    self._cookies[cn] = cv.value
                                logged_in = True
                                _LOGGER.info("DHL-Login erfolgreich via %s", endpoint)
                                break
                            except Exception as e:
                                _LOGGER.debug("JSON-Parsing fehlgeschlagen: %s", e)
                                # Auch ohne JSON-Token kann der Login via Cookie funktionieren
                                for cn, cv in resp.cookies.items():
                                    self._cookies[cn] = cv.value
                                if resp.cookies:
                                    logged_in = True
                                    break
                        elif resp.status in (401, 403):
                            raise DHLAuthError("Ungültige Zugangsdaten")
                except DHLAuthError:
                    raise
                except Exception as e:
                    _LOGGER.debug("Endpunkt %s fehlgeschlagen: %s", endpoint, e)
                    continue

            if not logged_in:
                # Letzter Versuch: Formular-basierter Login
                logged_in = await self._form_login(session)

            if not logged_in:
                raise DHLAuthError("Login fehlgeschlagen – bitte Zugangsdaten prüfen")

            return True

        except DHLAuthError:
            raise
        except Exception as e:
            _LOGGER.error("Unerwarteter Login-Fehler: %s", e)
            raise DHLAuthError(f"Login-Fehler: {e}") from e

    async def _form_login(self, session) -> bool:
        """Fallback: Formular-basierter Login."""
        try:
            form_data = {
                "username": self._username,
                "password": self._password,
            }
            form_headers = {
                **HEADERS,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            async with session.post(
                "https://www.dhl.de/de/privatkunden/dhl-kundenkonto/anmelden.html",
                data=form_data,
                headers=form_headers,
                cookies=self._cookies,
                allow_redirects=True,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                for cn, cv in resp.cookies.items():
                    self._cookies[cn] = cv.value
                # Prüfe ob wir eingeloggt sind (nicht mehr auf Login-Seite)
                final_url = str(resp.url)
                if "anmelden" not in final_url and resp.status == 200:
                    _LOGGER.info("DHL-Login via Formular erfolgreich")
                    return True
        except Exception as e:
            _LOGGER.debug("Formular-Login fehlgeschlagen: %s", e)
        return False

    async def async_get_shipments(self) -> list[DHLShipment]:
        """Lädt alle Sendungen aus dem DHL-Konto."""
        session = self._get_session()
        shipments = []

        api_headers = {
            **HEADERS,
            "X-Requested-With": "XMLHttpRequest",
        }
        if self._auth_token:
            api_headers["Authorization"] = f"Bearer {self._auth_token}"

        # Verschiedene API-Endpunkte für Sendungsliste
        endpoints = [
            "https://www.dhl.de/int-erkennen/rest/data?language=de&type=MY_DHL",
            "https://www.dhl.de/int-erkennen/rest/data?language=de",
            "https://www.dhl.de/int-webapp/spa/assets/api/my-shipments",
        ]

        for endpoint in endpoints:
            try:
                async with session.get(
                    endpoint,
                    headers=api_headers,
                    cookies=self._cookies,
                    allow_redirects=True,
                    timeout=REQUEST_TIMEOUT,
                ) as resp:
                    _LOGGER.debug("Sendungen-API %s: Status %s", endpoint, resp.status)
                    if resp.status == 200:
                        try:
                            data = await resp.json(content_type=None)
                            parsed = self._parse_api_response(data)
                            if parsed:
                                shipments = parsed
                                _LOGGER.info(
                                    "%d Sendungen via %s gefunden", len(shipments), endpoint
                                )
                                break
                        except Exception as e:
                            _LOGGER.debug("Parsing fehlgeschlagen für %s: %s", endpoint, e)
            except Exception as e:
                _LOGGER.debug("Endpunkt %s fehlgeschlagen: %s", endpoint, e)

        # Wenn keine Sendungen gefunden: gespeicherte Tracking-Nummern abfragen
        if not shipments:
            _LOGGER.warning(
                "Keine Sendungen via API gefunden – "
                "DHL hat möglicherweise die API-Struktur geändert."
            )

        return shipments

    def _parse_api_response(self, data: Any) -> list[DHLShipment]:
        """Parst die API-Antwort."""
        shipments = []

        if not isinstance(data, dict):
            return shipments

        # Verschiedene mögliche Keys
        raw_list = (
            data.get("sendungen")
            or data.get("shipments")
            or data.get("parcels")
            or data.get("items")
            or []
        )

        # Evtl. ist data selbst eine einzelne Sendung
        if not raw_list and (data.get("trackingNumber") or data.get("id")):
            raw_list = [data]

        for raw in raw_list:
            try:
                s = self._parse_single_shipment(raw)
                if s:
                    shipments.append(s)
            except Exception as e:
                _LOGGER.debug("Fehler beim Parsen: %s", e)

        return shipments

    def _parse_single_shipment(self, raw: dict) -> DHLShipment | None:
        """Parst eine einzelne Sendung."""
        if not isinstance(raw, dict):
            return None

        tracking_number = (
            raw.get("trackingNumber")
            or raw.get("id")
            or raw.get("shipmentId")
            or raw.get("barcode")
            or ""
        )
        if not tracking_number:
            return None

        # Status
        status_raw = raw.get("status") or raw.get("deliveryStatus") or {}
        if isinstance(status_raw, dict):
            status_text = status_raw.get("description", "Unbekannt")
            status_code = status_raw.get("status", "unknown")
        else:
            status_text = str(status_raw)
            status_code = str(status_raw)
        status = self._map_status(status_code)

        # Events
        events = []
        for ev in raw.get("events", raw.get("history", [])):
            if not isinstance(ev, dict):
                continue
            loc = ev.get("location", {})
            location_str = (
                loc.get("address", {}).get("addressLocality", "")
                if isinstance(loc, dict)
                else str(loc)
            )
            events.append(
                DHLShipmentEvent(
                    timestamp=ev.get("timestamp", ev.get("date", "")),
                    location=location_str,
                    description=ev.get("description", ev.get("status", "")),
                )
            )

        # Live-Status
        live = None
        live_raw = raw.get("liveTracking") or raw.get("live") or {}
        if isinstance(live_raw, dict) and live_raw:
            live = DHLLiveStatus(
                stops_remaining=live_raw.get("stopsRemaining"),
                estimated_delivery_start=live_raw.get("deliveryTimeStart"),
                estimated_delivery_end=live_raw.get("deliveryTimeEnd"),
                current_location=live_raw.get("currentLocation"),
                driver_name=live_raw.get("driverName"),
                map_url=live_raw.get("mapUrl"),
            )

        return DHLShipment(
            tracking_number=str(tracking_number),
            status=status,
            status_text=status_text,
            description=raw.get("description", raw.get("title", raw.get("productName", ""))),
            sender=raw.get("sender", raw.get("shipper")),
            recipient=raw.get("recipient"),
            estimated_delivery=raw.get(
                "estimatedTimeOfDelivery",
                raw.get("expectedDelivery", raw.get("estimatedDelivery")),
            ),
            delivery_date=raw.get("deliveryDate"),
            weight=str(raw.get("weight", "")),
            product=raw.get("product", raw.get("productName")),
            events=events,
            live_status=live,
        )

    def _map_status(self, code: str) -> str:
        code_lower = str(code).lower()
        if any(w in code_lower for w in ("delivered", "zugestellt")):
            return "delivered"
        if any(w in code_lower for w in ("out_for_delivery", "in_delivery", "in zustellung")):
            return "out_for_delivery"
        if any(w in code_lower for w in ("transit", "in_transit", "unterwegs")):
            return "in_transit"
        if any(w in code_lower for w in ("pre_transit", "announced", "angekündigt")):
            return "pre_transit"
        if any(w in code_lower for w in ("failed", "fehlgeschlagen")):
            return "delivery_failed"
        if any(w in code_lower for w in ("returned", "rücksendung")):
            return "returned"
        if any(w in code_lower for w in ("pickup", "abholung")):
            return "waiting_for_pickup"
        return "unknown"

    async def async_shutdown(self) -> None:
        """Nichts zu tun – Session wird von HA verwaltet."""
