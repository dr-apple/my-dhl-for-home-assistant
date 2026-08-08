"""Sensor-Entities für DHL Meine Sendungen."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ICON_MAP, STATUS_TRANSLATIONS
from .coordinator import DHLDataUpdateCoordinator
from .scraper import DHLShipment

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setzt Sensor-Entities auf."""
    coordinator: DHLDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Übersicht-Sensor (Anzahl aktiver Sendungen)
    entities: list[SensorEntity] = [DHLOverviewSensor(coordinator=coordinator, entry=entry)]

    # Einzelne Sendungs-Sensoren
    if coordinator.data:
        for tracking_number in coordinator.data:
            entities.append(
                DHLShipmentSensor(
                    coordinator=coordinator,
                    entry=entry,
                    tracking_number=tracking_number,
                )
            )

    async_add_entities(entities)

    known_tracking_numbers = set(coordinator.data or {})

    # Neue Sendungen dynamisch hinzufügen
    @callback
    def _async_add_new_shipments() -> None:
        new_entities: list[DHLShipmentSensor] = []
        if coordinator.data:
            for tracking_number in coordinator.data:
                if tracking_number in known_tracking_numbers:
                    continue
                known_tracking_numbers.add(tracking_number)
                new_entities.append(
                    DHLShipmentSensor(
                        coordinator=coordinator,
                        entry=entry,
                        tracking_number=tracking_number,
                    )
                )
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_shipments))


class DHLOverviewSensor(CoordinatorEntity[DHLDataUpdateCoordinator], SensorEntity):
    """Übersicht-Sensor: Zeigt Anzahl aktiver Sendungen."""

    _attr_icon = "mdi:package-variant-closed"
    _attr_native_unit_of_measurement = "Sendungen"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DHLDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_overview"
        self._attr_name = "Aktive Sendungen"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"DHL Konto ({entry.data.get('username', '')})",
            manufacturer="DHL",
            model="Meine Sendungen",
        )

    @property
    def native_value(self) -> int:
        """Anzahl aktiver Sendungen."""
        if not self.coordinator.data:
            return 0
        active_statuses = {
            "in_transit",
            "out_for_delivery",
            "pre_transit",
            "waiting_for_pickup",
        }
        return sum(
            1 for shipment in self.coordinator.data.values() if shipment.status in active_statuses
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Alle Sendungen als Attribut."""
        if not self.coordinator.data:
            return {"sendungen": []}

        return {
            "sendungen": [shipment.to_dict() for shipment in self.coordinator.data.values()],
            "gesamt": len(self.coordinator.data),
            "aktiv": self.native_value,
        }


class DHLShipmentSensor(CoordinatorEntity[DHLDataUpdateCoordinator], SensorEntity):
    """Sensor für eine einzelne DHL-Sendung."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DHLDataUpdateCoordinator,
        entry: ConfigEntry,
        tracking_number: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._tracking_number = tracking_number
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{tracking_number}"
        # Kurze ID für Entity-Name
        short_id = tracking_number[-6:] if len(tracking_number) > 6 else tracking_number
        self._attr_name = f"Sendung …{short_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"DHL Konto ({entry.data.get('username', '')})",
            manufacturer="DHL",
            model="Meine Sendungen",
        )

    @property
    def _shipment(self) -> DHLShipment | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._tracking_number)

    @property
    def native_value(self) -> str:
        """Aktueller Status der Sendung."""
        s = self._shipment
        if not s:
            return "Unbekannt"
        return STATUS_TRANSLATIONS.get(s.status, s.status_text or "Unbekannt")

    @property
    def icon(self) -> str:
        s = self._shipment
        if not s:
            return "mdi:package-variant"
        return ICON_MAP.get(s.status, "mdi:package-variant")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Alle Details der Sendung."""
        s = self._shipment
        if not s:
            return {}

        attrs: dict[str, Any] = {
            "tracking_number": s.tracking_number,
            "status": s.status,
            "status_text": s.status_text,
            "beschreibung": s.description,
        }

        if s.sender:
            attrs["absender"] = s.sender
        if s.recipient:
            attrs["empfaenger"] = s.recipient
        if s.estimated_delivery:
            attrs["voraussichtliche_lieferung"] = s.estimated_delivery
        if s.delivery_date:
            attrs["lieferdatum"] = s.delivery_date
        if s.weight:
            attrs["gewicht"] = s.weight
        if s.product:
            attrs["produkt"] = s.product

        # Sendungsereignisse
        if s.events:
            attrs["ereignisse"] = [e.to_dict() for e in s.events[:10]]
            attrs["letztes_ereignis"] = s.events[0].to_dict() if s.events else None

        # Live-Status (der interessante Teil!)
        if s.live_status:
            live = s.live_status
            attrs["live_tracking"] = True

            if live.stops_remaining is not None:
                attrs["stops_noch"] = live.stops_remaining
                attrs["stops_noch_text"] = (
                    f"Noch {live.stops_remaining} "
                    f"{'Stop' if live.stops_remaining == 1 else 'Stops'} vor dir"
                )

            if live.estimated_delivery_start and live.estimated_delivery_end:
                attrs["lieferzeitfenster"] = (
                    f"{live.estimated_delivery_start} – {live.estimated_delivery_end} Uhr"
                )
                attrs["lieferzeitfenster_start"] = live.estimated_delivery_start
                attrs["lieferzeitfenster_ende"] = live.estimated_delivery_end
            elif live.estimated_delivery_start:
                attrs["lieferzeitfenster"] = f"Ab {live.estimated_delivery_start} Uhr"

            if live.current_location:
                attrs["fahrer_position"] = live.current_location

            if live.driver_name:
                attrs["fahrer"] = live.driver_name

            if live.map_url:
                attrs["karte_url"] = live.map_url
        else:
            attrs["live_tracking"] = False

        # Tracking-URL
        attrs["tracking_url"] = (
            f"https://www.dhl.de/de/privatkunden/pakete-empfangen/verfolgen.html"
            f"?lang=de&idc={s.tracking_number}"
        )

        return attrs
