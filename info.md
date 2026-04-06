# DHL Meine Sendungen

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/dein-github-user/dhl-meine-sendungen-ha.svg)](https://github.com/dein-github-user/dhl-meine-sendungen-ha/releases)

Eine Home Assistant Integration, die sich in dein **DHL-Kundenkonto** (dhl.de) einloggt und alle Sendungen inklusive **Live-Status** abruft.

## Features

- 🔐 Automatischer Login mit deinen DHL-Zugangsdaten
- 📦 Alle Sendungen als Sensor-Entities in Home Assistant
- 🚚 **Live-Tracking** (wenn verfügbar):
  - Verbleibende Stops vor deiner Adresse
  - Lieferzeitfenster (z. B. „10:00 – 12:00 Uhr")
  - Aktuelle Fahrerposition
- 🔔 Automatisierungen & Push-Benachrichtigungen
- ⚙️ Vollständig über die HA-UI einrichtbar (kein YAML nötig)

## Voraussetzungen

Playwright muss auf deinem Home Assistant System installiert sein:

```bash
pip3 install playwright beautifulsoup4
playwright install chromium --with-deps
```

## Einrichtung

Nach der Installation über HACS:

1. HA neu starten
2. **Einstellungen → Geräte & Dienste → Integration hinzufügen**
3. Nach **„DHL Meine Sendungen"** suchen
4. DHL-E-Mail und Passwort eingeben

## Erstelle Sensoren

| Sensor | Beschreibung |
|---|---|
| `sensor.dhl_aktive_sendungen` | Anzahl aktiver Pakete |
| `sensor.dhl_sendung_…XXXXXX` | Status + Details pro Sendung |

### Live-Tracking Attribute

| Attribut | Beispiel |
|---|---|
| `stops_noch` | `3` |
| `stops_noch_text` | `Noch 3 Stops vor dir` |
| `lieferzeitfenster` | `10:00 – 12:00 Uhr` |
| `fahrer_position` | `Musterstraße, Darmstadt` |
| `letztes_ereignis` | Letzter Tracking-Event |
| `tracking_url` | Link zu dhl.de |
