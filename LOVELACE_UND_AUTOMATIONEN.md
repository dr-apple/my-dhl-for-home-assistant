# DHL Meine Sendungen - Lovelace & Automatisierungen

## Lovelace Dashboard Card

### Übersichtskarte (entities card)
```yaml
type: entities
title: 📦 DHL Sendungen
entities:
  - entity: sensor.dhl_aktive_sendungen
    name: Aktive Sendungen
show_header_toggle: false
```

### Sendungs-Detail Card (markdown)
```yaml
type: markdown
title: 📦 DHL Sendungsstatus
content: >
  {% set sendungen = state_attr('sensor.dhl_aktive_sendungen', 'sendungen') %}
  {% if sendungen %}
    {% for s in sendungen %}
  ---
  **{{ s.beschreibung or s.tracking_number }}**
  
  📍 Status: `{{ s.status_text }}`
  🔢 Tracking: `{{ s.tracking_number }}`
    {% if s.voraussichtliche_lieferung %}
  📅 Lieferung: {{ s.voraussichtliche_lieferung }}
    {% endif %}
    {% if s.live_status and s.stops_noch is defined %}
  🚚 **LIVE:** Noch **{{ s.stops_noch }} Stops** vor dir!
    {% endif %}
    {% if s.lieferzeitfenster is defined %}
  ⏰ Zeitfenster: {{ s.lieferzeitfenster }}
    {% endif %}
    {% endfor %}
  {% else %}
  Keine aktiven Sendungen.
  {% endif %}
```

### Custom Button Card (pro Sendung)
```yaml
type: custom:button-card
entity: sensor.dhl_sendung_xxxx   # ersetze xxxx mit letzten 6 Stellen der Tracking-Nr.
name: Mein Paket
icon: mdi:truck-fast
show_state: true
styles:
  card:
    - background-color: |
        [[[
          if (entity.state === 'In Zustellung heute') return '#ffd700';
          if (entity.state === 'Zugestellt') return '#90EE90';
          return 'var(--card-background-color)';
        ]]]
```

---

## Automatisierungen

### Benachrichtigung wenn Paket in Zustellung
```yaml
automation:
  - alias: "DHL - Paket in Zustellung"
    trigger:
      - platform: state
        entity_id: sensor.dhl_sendung_xxxx
        to: "In Zustellung heute"
    action:
      - service: notify.mobile_app_dein_handy
        data:
          title: "📦 DHL - Paket unterwegs!"
          message: >
            Dein Paket ist heute in Zustellung.
            {% set stops = state_attr('sensor.dhl_sendung_xxxx', 'stops_noch') %}
            {% if stops is not none %}
            Noch {{ stops }} Stops vor dir!
            {% endif %}
            {% set zeit = state_attr('sensor.dhl_sendung_xxxx', 'lieferzeitfenster') %}
            {% if zeit %}
            Zeitfenster: {{ zeit }}
            {% endif %}

  - alias: "DHL - Paket zugestellt"
    trigger:
      - platform: state
        entity_id: sensor.dhl_sendung_xxxx
        to: "Zugestellt"
    action:
      - service: notify.mobile_app_dein_handy
        data:
          title: "✅ DHL - Paket zugestellt!"
          message: "Dein Paket wurde zugestellt."

  - alias: "DHL - Live Stops Update"
    trigger:
      - platform: state
        entity_id: sensor.dhl_sendung_xxxx
        attribute: stops_noch
    condition:
      - condition: template
        value_template: >
          {{ state_attr('sensor.dhl_sendung_xxxx', 'stops_noch') | int(99) < 5 }}
    action:
      - service: notify.mobile_app_dein_handy
        data:
          title: "🚚 Bald da!"
          message: >
            Noch {{ state_attr('sensor.dhl_sendung_xxxx', 'stops_noch') }} Stops
            bis dein Paket kommt!
```

---

## Template Sensoren (configuration.yaml)

```yaml
template:
  - sensor:
      - name: "DHL Nächste Lieferung"
        unique_id: dhl_next_delivery
        state: >
          {% set sendungen = state_attr('sensor.dhl_aktive_sendungen', 'sendungen') %}
          {% set active = sendungen | selectattr('status', 'in', ['out_for_delivery', 'in_transit']) | list %}
          {% if active | length > 0 %}
            {{ active[0].status_text }}
          {% else %}
            Keine aktive Lieferung
          {% endif %}
        icon: mdi:truck-delivery
        attributes:
          stops_noch: >
            {% set sendungen = state_attr('sensor.dhl_aktive_sendungen', 'sendungen') %}
            {% set active = sendungen | selectattr('live_tracking', 'equalto', true) | list %}
            {% if active | length > 0 and active[0].stops_noch is defined %}
              {{ active[0].stops_noch }}
            {% else %}
              null
            {% endif %}
          zeitfenster: >
            {% set sendungen = state_attr('sensor.dhl_aktive_sendungen', 'sendungen') %}
            {% set active = sendungen | selectattr('lieferzeitfenster', 'defined') | list %}
            {% if active | length > 0 %}
              {{ active[0].lieferzeitfenster }}
            {% else %}
              Nicht verfügbar
            {% endif %}
```
