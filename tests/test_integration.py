"""Tests for DHL Meine Sendungen."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ConfigEntryAuthFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dhl_meine_sendungen.const import DOMAIN
from custom_components.dhl_meine_sendungen.coordinator import DHLDataUpdateCoordinator
from custom_components.dhl_meine_sendungen.scraper import (
    DHLAuthError,
    DHLLiveStatus,
    DHLScraper,
    DHLShipment,
)


def _shipment(tracking_number: str = "00340434161094000000") -> DHLShipment:
    return DHLShipment(
        tracking_number=tracking_number,
        status="out_for_delivery",
        status_text="In Zustellung",
        description="Paket",
        sender="Versender",
        recipient="Empfänger",
        live_status=DHLLiveStatus(
            stops_remaining=3,
            driver_name="Fahrer",
            map_url="https://example.com/map",
        ),
    )


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data={"username": "test@example.com", "password": "secret"},
    )


@pytest.mark.asyncio
async def test_setup_and_dynamic_shipment(hass) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    first = _shipment()

    with (
        patch.object(DHLScraper, "async_login", AsyncMock(return_value=True)),
        patch.object(DHLScraper, "async_get_shipments", AsyncMock(return_value=[first])),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert len(hass.states.async_entity_ids("sensor")) == 2

    shipment_state = hass.states.get("sensor.dhl_konto_test_example_com_sendung_000000")
    assert shipment_state is not None
    assert shipment_state.attributes["empfaenger"] == "Empfänger"
    assert shipment_state.attributes["fahrer"] == "Fahrer"
    assert shipment_state.attributes["karte_url"] == "https://example.com/map"

    coordinator = hass.data[DOMAIN][entry.entry_id]
    second = _shipment("00340434161094123456")
    coordinator.async_set_updated_data(
        {first.tracking_number: first, second.tracking_number: second}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("sensor")) == 3


def test_parse_optional_recipient_and_live_fields(hass) -> None:
    scraper = DHLScraper(hass, "user", "password")
    shipment = scraper._parse_single_shipment(
        {
            "trackingNumber": "123",
            "status": {"status": "out_for_delivery", "description": "Unterwegs"},
            "recipient": "Ada Lovelace",
            "liveTracking": {
                "driverName": "Max",
                "mapUrl": "https://example.com/live",
            },
        }
    )

    assert shipment is not None
    assert shipment.recipient == "Ada Lovelace"
    assert shipment.live_status is not None
    assert shipment.live_status.driver_name == "Max"
    assert shipment.live_status.map_url == "https://example.com/live"


@pytest.mark.asyncio
async def test_auth_failure_requests_reauthentication(hass) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    coordinator = DHLDataUpdateCoordinator(hass, entry, scan_interval=None)
    coordinator._scraper.async_login = AsyncMock(side_effect=DHLAuthError("invalid"))

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
