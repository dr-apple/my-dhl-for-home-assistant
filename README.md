# DHL Meine Sendungen 📦

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/dein-github-user/dhl-meine-sendungen-ha.svg)](https://github.com/dein-github-user/dhl-meine-sendungen-ha/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Home Assistant Custom Integration – loggt sich bei **dhl.de** ein und liest alle Sendungen inklusive Live-Status (Stops, Zeitfenster, Fahrerposition) aus.

---

## Installation via HACS

### Schritt 1 – HACS Custom Repository hinzufügen

1. HACS öffnen → **Integrationen**
2. Oben rechts auf **⋮ → Benutzerdefinierte Repositories**
3. URL eingeben:
   ```
   https://github.com/dein-github-user/dhl-meine-sendungen-ha
   ```
4. Kategorie: **Integration** → **Hinzufügen**

### Schritt 2 – Integration installieren

1. In HACS nach **„DHL Meine Sendungen"** suchen
2. **Herunterladen** klicken
3. Home Assistant neu starten

### Schritt 3 – Playwright installieren

Playwright wird für die Browser-Automatisierung benötigt (DHL nutzt eine JavaScript-SPA).

**Bei Home Assistant OS** – Terminal / SSH Add-on:
```bash
pip3 install playwright beautifulsoup4
playwright install chromium --with-deps
```

**Bei Home Assistant Supervised / Container:**
```bash
docker exec -it homeassistant bash
pip3 install playwright beautifulsoup4
playwright install chromium
playwright install-deps chromium
```

### Schritt 4 – Integration einrichten

1. **Einstellungen → Geräte & Dienste → + Integration hinzufügen**
2. Nach **„DHL Meine Sendungen"** suchen
3. DHL-Zugangsdaten (E-Mail + Passwort von dhl.de) eingeben
4. ✅ Fertig – Sendungen erscheinen automatisch als Sensoren

---

## Verfügbare Entitäten

### Übersicht-Sensor
**`sensor.dhl_aktive_sendungen`**
- State: Anzahl aktiver Sendungen
- Attribute: `sendungen` (Liste), `gesamt`, `aktiv`

### Sendungs-Sensoren (automatisch pro Paket)
**`sensor.dhl_sendung_…XXXXXX`**

| Attribut | Beschreibung |
|---|---|
| `tracking_number` | Vollständige Tracking-Nummer |
| `beschreibung` | Absender / Sendungsbeschreibung |
| `voraussichtliche_lieferung` | Voraussichtliches Datum |
| `live_tracking` | `true` wenn Live-Status aktiv |
| `stops_noch` | Verbleibende Stops (Live) |
| `stops_noch_text` | „Noch 3 Stops vor dir" |
| `lieferzeitfenster` | „10:00 – 12:00 Uhr" |
| `fahrer_position` | Aktuelle Fahrerposition |
| `ereignisse` | Letzte 10 Tracking-Events |
| `tracking_url` | Direktlink zu dhl.de |

---

## Lovelace Karte

```yaml
type: markdown
title: 📦 DHL Sendungen
content: >
  {% set sendungen = state_attr('sensor.dhl_aktive_sendungen', 'sendungen') %}
  {% if sendungen %}
    {% for s in sendungen %}
  ---
  **{{ s.beschreibung or s.tracking_number }}**
  📍 `{{ s.status_text }}`
      {% if s.live_tracking %}
  🚚 **Noch {{ s.stops_noch }} Stops!**
  ⏰ {{ s.lieferzeitfenster }}
      {% elif s.voraussichtliche_lieferung %}
  📅 {{ s.voraussichtliche_lieferung }}
      {% endif %}
    {% endfor %}
  {% else %}
  Keine aktiven Sendungen.
  {% endif %}
```

---

## Bekannte Einschränkungen

- **2-Faktor-Authentifizierung** muss im DHL-Konto deaktiviert sein
- **Live-Tracking** ist nur am Liefertag nach dem Einscannen beim Fahrer verfügbar
- DHL kann ihre Website-Struktur ändern – bitte [Issue erstellen](https://github.com/dein-github-user/dhl-meine-sendungen-ha/issues)

---

## GitHub-Veröffentlichung

> **Ersetze `dein-github-user`** in allen Dateien mit deinem echten GitHub-Benutzernamen!

### Release-Tag für HACS erstellen
```
GitHub → Releases → New Release → Tag: v1.0.0
```
HACS erkennt neue Versionen automatisch über Git-Tags.

---

## Lizenz

MIT License – siehe [LICENSE](LICENSE)
