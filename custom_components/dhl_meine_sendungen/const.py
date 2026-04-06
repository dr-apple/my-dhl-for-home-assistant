"""Constants for the DHL Meine Sendungen integration."""

DOMAIN = "dhl_meine_sendungen"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 30  # minutes

DHL_LOGIN_URL = "https://www.dhl.de/de/privatkunden/dhl-kundenkonto/anmelden.html"
DHL_SENDUNGEN_URL = "https://www.dhl.de/de/privatkunden/pakete-empfangen/verfolgen.html"
DHL_MEINE_SENDUNGEN_URL = "https://www.dhl.de/de/privatkunden/dhl-kundenkonto/meine-sendungen.html"
DHL_TRACKING_API = "https://api-eu.dhl.com/track/shipments"

STATUS_TRANSLATIONS = {
    "delivered": "Zugestellt",
    "in_transit": "In Zustellung",
    "out_for_delivery": "In Zustellung heute",
    "waiting_for_pickup": "Wartet auf Abholung",
    "delivery_failed": "Zustellung fehlgeschlagen",
    "returned": "Rücksendung",
    "unknown": "Unbekannt",
    "pre_transit": "Versandankündigung",
    "transit": "In Bearbeitung",
}

ICON_MAP = {
    "delivered": "mdi:package-variant-closed-check",
    "in_transit": "mdi:truck-delivery",
    "out_for_delivery": "mdi:truck-fast",
    "waiting_for_pickup": "mdi:package-variant",
    "delivery_failed": "mdi:package-variant-closed-remove",
    "returned": "mdi:package-variant-remove",
    "unknown": "mdi:help-circle",
    "pre_transit": "mdi:package-variant-closed",
    "transit": "mdi:transit-connection-variant",
}
