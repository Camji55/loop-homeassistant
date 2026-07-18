"""Constants for the Loop integration."""

DOMAIN = "loop"

CONF_WEBHOOK_ID = "webhook_id"
CONF_NAME = "name"

KEY_SOURCE = "source"


def signal_update(entry_id: str) -> str:
    """Per-entry dispatcher signal, so each AID instance only updates its own entities."""
    return f"{DOMAIN}_data_updated_{entry_id}"

# Top-level keys in the payload Loop's HomeAssistantService sends.
KEY_GLUCOSE = "glucose"
KEY_DOSES = "doses"
KEY_CARBS = "carbs"
KEY_PUMP_EVENTS = "pump_events"
KEY_DOSING_DECISION = "dosing_decision"
KEY_STATUS = "status"
KEY_OVERRIDE = "override"
KEY_ALERTS = "alerts"
KEY_SETTINGS = "settings"
KEY_CGM_EVENTS = "cgm_events"
