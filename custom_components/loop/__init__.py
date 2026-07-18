"""The Loop integration.

Receives pushed data from the Loop iOS app's HomeAssistantService plugin
via a Home Assistant webhook and exposes it as sensors.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from aiohttp import web

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_WEBHOOK_ID,
    DOMAIN,
    KEY_ALERTS,
    KEY_CARBS,
    KEY_DOSES,
    KEY_DOSING_DECISION,
    KEY_GLUCOSE,
    KEY_OVERRIDE,
    KEY_PUMP_EVENTS,
    KEY_SETTINGS,
    KEY_STATUS,
    SIGNAL_UPDATE,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor"]

EVENT_DATA_RECEIVED = f"{DOMAIN}_data_received"


class LoopData:
    """Holds the most recent state pushed from Loop."""

    def __init__(self) -> None:
        self.latest_glucose: dict[str, Any] | None = None
        self.dosing_decision: dict[str, Any] | None = None
        self.status: dict[str, Any] | None = None
        self.override: dict[str, Any] | None = None
        self.last_carb_entry: dict[str, Any] | None = None
        self.last_bolus: dict[str, Any] | None = None
        self.settings: dict[str, Any] | None = None
        self.last_alert: dict[str, Any] | None = None

    def update(self, payload: dict[str, Any]) -> None:
        """Merge a webhook payload into the current state."""
        glucose = payload.get(KEY_GLUCOSE) or []
        if glucose:
            # Samples are sent oldest-first; keep the newest.
            self.latest_glucose = max(glucose, key=lambda s: s.get("date", ""))

        if payload.get(KEY_DOSING_DECISION):
            self.dosing_decision = payload[KEY_DOSING_DECISION]

        if payload.get(KEY_STATUS):
            # Status arrives piecemeal (dosing decisions vs. settings), so merge.
            self.status = {**(self.status or {}), **payload[KEY_STATUS]}

        if KEY_OVERRIDE in payload:
            # Explicit null means "no active override".
            self.override = payload[KEY_OVERRIDE]

        carbs = payload.get(KEY_CARBS) or []
        if carbs:
            self.last_carb_entry = max(carbs, key=lambda c: c.get("date", ""))

        boluses = [d for d in (payload.get(KEY_DOSES) or []) if d.get("type") == "bolus"]
        if boluses:
            self.last_bolus = max(boluses, key=lambda d: d.get("start_date", ""))

        if payload.get(KEY_SETTINGS):
            self.settings = payload[KEY_SETTINGS]

        alerts = payload.get(KEY_ALERTS) or []
        if alerts:
            # Prefer the newest alert that hasn't been retracted.
            unretracted = [a for a in alerts if not a.get("retracted_date")]
            self.last_alert = max(
                unretracted or alerts, key=lambda a: a.get("issued_date", "")
            )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Loop from a config entry."""
    data = LoopData()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = data

    webhook.async_register(
        hass,
        DOMAIN,
        "Loop",
        entry.data[CONF_WEBHOOK_ID],
        _make_webhook_handler(entry.entry_id),
        allowed_methods=["POST"],
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


def _make_webhook_handler(entry_id: str):
    """Create a webhook handler bound to a config entry."""

    async def handle_webhook(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        try:
            payload = await request.json()
        except ValueError:
            _LOGGER.warning("Loop webhook received non-JSON payload")
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        if not isinstance(payload, dict):
            return web.Response(status=HTTPStatus.BAD_REQUEST)

        _LOGGER.debug("Loop webhook payload: %s", payload)

        data: LoopData = hass.data[DOMAIN][entry_id]
        data.update(payload)

        # Notify entities, then fire a bus event for automations that want
        # the raw payload (e.g. reacting to individual pump events).
        async_dispatcher_send(hass, SIGNAL_UPDATE)
        hass.bus.async_fire(
            EVENT_DATA_RECEIVED,
            {
                "keys": sorted(payload.keys()),
                "pump_events": payload.get(KEY_PUMP_EVENTS) or [],
            },
        )
        for alert in payload.get(KEY_ALERTS) or []:
            hass.bus.async_fire(f"{DOMAIN}_alert", alert)
        return web.Response(status=HTTPStatus.OK)

    return handle_webhook
