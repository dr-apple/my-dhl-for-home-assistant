"""DHL Website Scraper - Login und Sendungsverfolgung."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

_LOGGER = logging.getLogger(__name__)


@dataclass
class DHLShipmentEvent:
    """Einzelnes Ereignis in der Sendungsverfolgung."""
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
    """Live-Status einer Sendung (wenn verfügbar)."""
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
    """Eine DHL-Sendung mit allen Informationen."""
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
    raw_data: dict = field(default_factory=dict)

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
    """Fehler bei der DHL-Authentifizierung."""


class DHLScraper:
    """
    DHL Sendungsverfolgung via Playwright Browser-Automatisierung.

    Loggt sich in das DHL-Kundenkonto ein und liest alle aktiven Sendungen aus.
    Nutzt Playwright für JavaScript-rendering da die DHL-Website eine SPA ist.
    """

    LOGIN_URL = "https://www.dhl.de/de/privatkunden/dhl-kundenkonto/anmelden.html"
    MEINE_SENDUNGEN_URL = "https://www.dhl.de/de/privatkunden/dhl-kundenkonto/meine-sendungen.html"
    TRACKING_BASE_URL = "https://www.dhl.de/de/privatkunden/pakete-empfangen/verfolgen.html"
    LIVE_TRACKING_API = "https://livetracking.dhl.de/api/v1"

    def __init__(self, username: str, password: str) -> None:
        self.username = username
        self.password = password
        self._browser = None
        self._context = None
        self._page = None

    async def async_init(self) -> None:
        """Initialisiert den Playwright-Browser."""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            self._context = await self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
                locale="de-DE",
            )
            self._page = await self._context.new_page()
            _LOGGER.debug("Playwright Browser initialisiert.")
        except ImportError:
            raise ImportError(
                "Playwright ist nicht installiert. "
                "Führe 'playwright install chromium' aus."
            )

    async def async_login(self) -> bool:
        """Loggt sich bei DHL ein. Returns True bei Erfolg."""
        if not self._page:
            await self.async_init()

        _LOGGER.debug("Versuche DHL-Login für %s", self.username)

        try:
            # Zur Login-Seite navigieren
            await self._page.goto(self.LOGIN_URL, wait_until="networkidle", timeout=30000)

            # Cookie-Banner wegklicken falls vorhanden
            await self._dismiss_cookie_banner()

            # Warte auf Login-Formular
            await self._page.wait_for_selector(
                'input[name="username"], input[id*="username"], input[type="email"]',
                timeout=10000,
            )

            # Username eingeben
            username_selector = await self._find_selector([
                'input[name="username"]',
                'input[id*="username"]',
                'input[autocomplete="username"]',
                'input[type="email"]',
            ])
            await self._page.fill(username_selector, self.username)
            await asyncio.sleep(0.5)

            # Weiter-Button oder direkt Passwort
            next_button = await self._page.query_selector(
                'button[type="submit"]:not([id*="password"]), '
                'button:has-text("Weiter"), '
                'button:has-text("Nächste")'
            )
            if next_button:
                await next_button.click()
                await asyncio.sleep(1)

            # Passwort eingeben
            password_selector = await self._find_selector([
                'input[name="password"]',
                'input[type="password"]',
                'input[id*="password"]',
                'input[autocomplete="current-password"]',
            ])
            await self._page.fill(password_selector, self.password)
            await asyncio.sleep(0.3)

            # Login-Button klicken
            login_button = await self._find_selector([
                'button[type="submit"]',
                'button:has-text("Anmelden")',
                'button:has-text("Einloggen")',
                'input[type="submit"]',
            ])
            await self._page.click(login_button)

            # Warte auf Redirect nach Login
            await self._page.wait_for_load_state("networkidle", timeout=20000)

            # Prüfe ob Login erfolgreich
            current_url = self._page.url
            if "anmelden" in current_url or "login" in current_url.lower():
                # Eventuell Fehlermeldung
                error_msg = await self._page.query_selector(
                    '.error-message, .alert-danger, [class*="error"]'
                )
                if error_msg:
                    error_text = await error_msg.inner_text()
                    raise DHLAuthError(f"Login fehlgeschlagen: {error_text}")
                raise DHLAuthError("Login fehlgeschlagen - Ungültige Anmeldedaten?")

            _LOGGER.info("DHL-Login erfolgreich für %s", self.username)
            return True

        except DHLAuthError:
            raise
        except Exception as e:
            _LOGGER.error("Fehler beim DHL-Login: %s", e)
            raise DHLAuthError(f"Login-Fehler: {e}") from e

    async def async_get_shipments(self) -> list[DHLShipment]:
        """Liest alle Sendungen aus dem DHL-Konto aus."""
        if not self._page:
            await self.async_login()

        _LOGGER.debug("Rufe DHL Meine Sendungen ab...")
        shipments = []

        try:
            await self._page.goto(
                self.MEINE_SENDUNGEN_URL,
                wait_until="networkidle",
                timeout=30000,
            )

            # Falls nicht eingeloggt, nochmal einloggen
            if "anmelden" in self._page.url.lower():
                await self.async_login()
                await self._page.goto(
                    self.MEINE_SENDUNGEN_URL,
                    wait_until="networkidle",
                    timeout=30000,
                )

            await asyncio.sleep(2)  # Warte auf dynamischen Inhalt

            # Versuche Sendungsdaten aus JSON-State zu extrahieren (schnellster Weg)
            shipments = await self._extract_from_page_state()

            if not shipments:
                # Fallback: DOM-Parsing
                shipments = await self._extract_from_dom()

            # Für jede aktive Sendung: Live-Status abrufen
            for shipment in shipments:
                if shipment.status in ("out_for_delivery", "in_transit"):
                    try:
                        live = await self._get_live_status(shipment.tracking_number)
                        if live:
                            shipment.live_status = live
                    except Exception as e:
                        _LOGGER.debug(
                            "Kein Live-Status für %s: %s",
                            shipment.tracking_number, e
                        )

            _LOGGER.info("Erfolgreich %d Sendungen abgerufen.", len(shipments))
            return shipments

        except DHLAuthError:
            raise
        except Exception as e:
            _LOGGER.error("Fehler beim Abrufen der Sendungen: %s", e)
            return []

    async def _extract_from_page_state(self) -> list[DHLShipment]:
        """Extrahiert Sendungen aus dem JavaScript-State der SPA."""
        shipments = []
        try:
            # Viele React/Vue SPAs speichern State in window.__STATE__ o.ä.
            state_data = await self._page.evaluate("""
                () => {
                    // Versuche verschiedene State-Quellen
                    const sources = [
                        window.__INITIAL_STATE__,
                        window.__APP_STATE__,
                        window.__NEXT_DATA__,
                        window.dhlAppData,
                        window.shipmentData,
                    ];
                    for (const src of sources) {
                        if (src) return JSON.stringify(src);
                    }

                    // Suche in Script-Tags nach eingebettetem JSON
                    const scripts = document.querySelectorAll('script[type="application/json"], script[id*="data"]');
                    for (const script of scripts) {
                        try {
                            const parsed = JSON.parse(script.textContent);
                            if (parsed && (parsed.shipments || parsed.parcels || parsed.sendungen)) {
                                return JSON.stringify(parsed);
                            }
                        } catch(e) {}
                    }
                    return null;
                }
            """)

            if state_data:
                data = json.loads(state_data)
                raw_shipments = (
                    data.get("shipments") or
                    data.get("parcels") or
                    data.get("sendungen") or
                    []
                )
                for raw in raw_shipments:
                    s = self._parse_raw_shipment(raw)
                    if s:
                        shipments.append(s)

        except Exception as e:
            _LOGGER.debug("State-Extraktion fehlgeschlagen: %s", e)

        return shipments

    async def _extract_from_dom(self) -> list[DHLShipment]:
        """Extrahiert Sendungen per DOM-Parsing."""
        from bs4 import BeautifulSoup

        shipments = []
        try:
            html = await self._page.content()
            soup = BeautifulSoup(html, "html.parser")

            # DHL-spezifische Selektoren (können sich ändern)
            shipment_cards = soup.select(
                "[class*='shipment-card'], "
                "[class*='parcel-card'], "
                "[class*='sendung'], "
                "[data-testid*='shipment'], "
                ".tracking-item, "
                "[class*='tracking-result']"
            )

            for card in shipment_cards:
                try:
                    shipment = await self._parse_dom_card(card)
                    if shipment:
                        shipments.append(shipment)
                except Exception as e:
                    _LOGGER.debug("Fehler beim Parsen einer Sendungskarte: %s", e)

            # Wenn keine Karten gefunden, suche nach Tracking-Nummern
            if not shipments:
                tracking_pattern = re.compile(
                    r'\b(JD\d{18}|\d{20}|[A-Z]{2}\d{9}[A-Z]{2}|'
                    r'GM\d{18}|LX\d{9}DE)\b'
                )
                text = soup.get_text()
                tracking_numbers = list(set(tracking_pattern.findall(text)))
                _LOGGER.debug(
                    "Gefundene Tracking-Nummern im DOM: %s", tracking_numbers
                )
                for tn in tracking_numbers[:20]:  # Max 20
                    try:
                        s = await self._get_tracking_details(tn)
                        if s:
                            shipments.append(s)
                    except Exception:
                        pass

        except Exception as e:
            _LOGGER.error("DOM-Parsing fehlgeschlagen: %s", e)

        return shipments

    async def _parse_dom_card(self, card) -> DHLShipment | None:
        """Parst eine einzelne Sendungskarte aus dem DOM."""
        # Tracking-Nummer extrahieren
        tn_elem = card.select_one(
            "[class*='tracking-number'], [data-tracking], "
            "[class*='shipment-id'], [class*='parcel-id']"
        )
        if not tn_elem:
            return None

        tracking_number = tn_elem.get_text(strip=True) or tn_elem.get("data-tracking", "")
        if not tracking_number:
            return None

        # Status
        status_elem = card.select_one(
            "[class*='status'], [class*='state'], "
            "[data-status], [class*='delivery-status']"
        )
        status_text = status_elem.get_text(strip=True) if status_elem else "Unbekannt"
        status = self._map_status_text(status_text)

        # Beschreibung/Absender
        desc_elem = card.select_one(
            "[class*='description'], [class*='sender'], "
            "[class*='title'], [class*='name']"
        )
        description = desc_elem.get_text(strip=True) if desc_elem else ""

        # Lieferdatum
        date_elem = card.select_one(
            "[class*='date'], [class*='delivery-date'], "
            "[class*='estimated']"
        )
        estimated = date_elem.get_text(strip=True) if date_elem else None

        return DHLShipment(
            tracking_number=tracking_number,
            status=status,
            status_text=status_text,
            description=description,
            estimated_delivery=estimated,
        )

    def _parse_raw_shipment(self, raw: dict) -> DHLShipment | None:
        """Parst ein rohes Sendungs-Dict."""
        try:
            tracking_number = (
                raw.get("trackingNumber") or
                raw.get("id") or
                raw.get("shipmentId") or
                raw.get("barcode") or
                ""
            )
            if not tracking_number:
                return None

            status_raw = (
                raw.get("status") or
                raw.get("deliveryStatus") or
                raw.get("state") or
                "unknown"
            )
            if isinstance(status_raw, dict):
                status_text = status_raw.get("description", "Unbekannt")
                status = self._map_status_code(status_raw.get("status", ""))
            else:
                status_text = str(status_raw)
                status = self._map_status_code(status_raw)

            events = []
            for event in raw.get("events", raw.get("history", [])):
                events.append(DHLShipmentEvent(
                    timestamp=event.get("timestamp", event.get("date", "")),
                    location=event.get("location", {}).get("address", {}).get("addressLocality", "")
                              if isinstance(event.get("location"), dict)
                              else event.get("location", ""),
                    description=event.get("description", event.get("status", "")),
                ))

            return DHLShipment(
                tracking_number=str(tracking_number),
                status=status,
                status_text=status_text,
                description=raw.get("description", raw.get("title", "")),
                sender=raw.get("sender", raw.get("shipper", "")),
                recipient=raw.get("recipient", ""),
                estimated_delivery=raw.get(
                    "estimatedTimeOfDelivery",
                    raw.get("expectedDelivery", raw.get("estimatedDelivery"))
                ),
                delivery_date=raw.get("deliveryDate"),
                weight=raw.get("weight"),
                product=raw.get("product", raw.get("productName")),
                events=events,
                raw_data=raw,
            )
        except Exception as e:
            _LOGGER.debug("Fehler beim Parsen von Sendungsdaten: %s", e)
            return None

    async def _get_tracking_details(self, tracking_number: str) -> DHLShipment | None:
        """Ruft Details für eine einzelne Sendung ab."""
        try:
            # Navigiere zur Tracking-Seite
            url = f"{self.TRACKING_BASE_URL}?lang=de&idc={tracking_number}"
            response_data = await self._page.evaluate(f"""
                async () => {{
                    const resp = await fetch(
                        'https://www.dhl.de/int-erkennen/rest/data?trackingNumber={tracking_number}&language=de',
                        {{credentials: 'include'}}
                    );
                    if (!resp.ok) return null;
                    return await resp.json();
                }}
            """)

            if response_data:
                shipments_data = (
                    response_data.get("sendungen") or
                    response_data.get("shipments") or
                    []
                )
                if shipments_data:
                    return self._parse_raw_shipment(shipments_data[0])

        except Exception as e:
            _LOGGER.debug("Tracking-Details für %s fehlgeschlagen: %s", tracking_number, e)

        return None

    async def _get_live_status(self, tracking_number: str) -> DHLLiveStatus | None:
        """Ruft den Live-Tracking-Status ab (Stops, Zeitfenster, etc.)."""
        try:
            # DHL Live-Tracking API
            live_data = await self._page.evaluate(f"""
                async () => {{
                    // Versuche Live-Tracking-API
                    const urls = [
                        'https://livetracking.dhl.de/api/v1/shipments/{tracking_number}',
                        'https://www.dhl.de/int-erkennen/rest/data?trackingNumber={tracking_number}&language=de&type=live',
                    ];
                    for (const url of urls) {{
                        try {{
                            const resp = await fetch(url, {{credentials: 'include'}});
                            if (resp.ok) return await resp.json();
                        }} catch(e) {{}}
                    }}
                    return null;
                }}
            """)

            if not live_data:
                return None

            live = DHLLiveStatus()

            # Stops remaining
            live.stops_remaining = (
                live_data.get("stopsRemaining") or
                live_data.get("remainingStops") or
                live_data.get("stopsBefore")
            )

            # Zeitfenster
            time_window = live_data.get("deliveryTimeframe", live_data.get("timeWindow", {}))
            if isinstance(time_window, dict):
                live.estimated_delivery_start = time_window.get("start", time_window.get("from"))
                live.estimated_delivery_end = time_window.get("end", time_window.get("to"))
            elif isinstance(time_window, str):
                # Format: "10:00-12:00"
                parts = time_window.split("-")
                if len(parts) == 2:
                    live.estimated_delivery_start = parts[0].strip()
                    live.estimated_delivery_end = parts[1].strip()

            # Aktuelle Position
            location = live_data.get("currentLocation", live_data.get("location", {}))
            if isinstance(location, dict):
                addr = location.get("address", {})
                live.current_location = (
                    f"{addr.get('street', '')} {addr.get('addressLocality', '')}".strip()
                )
            elif isinstance(location, str):
                live.current_location = location

            # Map URL
            live.map_url = live_data.get("mapUrl", live_data.get("trackingUrl"))

            return live if any([
                live.stops_remaining is not None,
                live.estimated_delivery_start,
                live.current_location,
            ]) else None

        except Exception as e:
            _LOGGER.debug("Live-Status Fehler für %s: %s", tracking_number, e)
            return None

    async def _dismiss_cookie_banner(self) -> None:
        """Schließt Cookie-Banner wenn vorhanden."""
        try:
            cookie_selectors = [
                'button[id*="accept"], button[class*="accept"]',
                'button:has-text("Alle akzeptieren")',
                'button:has-text("Akzeptieren")',
                'button:has-text("Zustimmen")',
                'button[data-testid*="accept-all"]',
                '#onetrust-accept-btn-handler',
                '.cookie-consent-accept',
            ]
            for selector in cookie_selectors:
                try:
                    btn = await self._page.wait_for_selector(
                        selector, timeout=3000
                    )
                    if btn:
                        await btn.click()
                        await asyncio.sleep(0.5)
                        return
                except Exception:
                    continue
        except Exception:
            pass

    async def _find_selector(self, selectors: list[str]) -> str:
        """Findet den ersten verfügbaren Selektor."""
        for selector in selectors:
            try:
                elem = await self._page.query_selector(selector)
                if elem:
                    return selector
            except Exception:
                continue
        return selectors[0]  # Fallback

    def _map_status_code(self, code: str) -> str:
        """Mappt DHL-Statuscodes auf interne Status."""
        code_lower = str(code).lower()
        mapping = {
            "delivered": "delivered",
            "zugestellt": "delivered",
            "out_for_delivery": "out_for_delivery",
            "in_delivery": "out_for_delivery",
            "in zustellung": "out_for_delivery",
            "transit": "in_transit",
            "in_transit": "in_transit",
            "in bearbeitung": "in_transit",
            "pre_transit": "pre_transit",
            "versandankündigung": "pre_transit",
            "failed": "delivery_failed",
            "delivery_failed": "delivery_failed",
            "zustellung fehlgeschlagen": "delivery_failed",
            "returned": "returned",
            "rücksendung": "returned",
            "pickup": "waiting_for_pickup",
            "waiting_for_pickup": "waiting_for_pickup",
        }
        for key, value in mapping.items():
            if key in code_lower:
                return value
        return "unknown"

    def _map_status_text(self, text: str) -> str:
        """Mappt deutschen Statustext auf internen Status."""
        return self._map_status_code(text)

    async def async_shutdown(self) -> None:
        """Schließt den Browser."""
        try:
            if self._browser:
                await self._browser.close()
            if hasattr(self, "_playwright"):
                await self._playwright.stop()
        except Exception as e:
            _LOGGER.debug("Fehler beim Schließen des Browsers: %s", e)
