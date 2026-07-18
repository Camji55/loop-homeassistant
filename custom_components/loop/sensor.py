"""Sensors for the Loop integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import LoopData
from .const import DOMAIN, signal_update


@dataclass(frozen=True, kw_only=True)
class LoopSensorDescription(SensorEntityDescription):
    """Describes a Loop sensor with its value extractor."""

    value_fn: Callable[[LoopData], Any]
    attrs_fn: Callable[[LoopData], dict[str, Any]] | None = None


# Loop's own trend glyphs (LoopKit GlucoseTrend.symbol)
TREND_ARROWS = {
    "upUpUp": "⇈",
    "upUp": "↑",
    "up": "↗︎",
    "flat": "→",
    "down": "↘︎",
    "downDown": "↓",
    "downDownDown": "⇊",
}


def _glucose(data: LoopData) -> Any:
    return (data.latest_glucose or {}).get("value_mgdl")


def _glucose_attrs(data: LoopData) -> dict[str, Any]:
    sample = data.latest_glucose or {}
    return {
        "trend": sample.get("trend"),
        "trend_arrow": TREND_ARROWS.get(sample.get("trend"), ""),
        "trend_rate_mgdl_per_min": sample.get("trend_rate_mgdl_per_min"),
        "sample_date": sample.get("date"),
        "device": sample.get("device"),
    }


def _decision(data: LoopData, key: str) -> Any:
    return (data.dosing_decision or {}).get(key)


def _status(data: LoopData, key: str) -> Any:
    return (data.status or {}).get(key)


SENSORS: tuple[LoopSensorDescription, ...] = (
    LoopSensorDescription(
        key="blood_glucose",
        translation_key="blood_glucose",
        native_unit_of_measurement="mg/dL",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water",
        value_fn=_glucose,
        attrs_fn=_glucose_attrs,
    ),
    LoopSensorDescription(
        key="glucose_trend",
        translation_key="glucose_trend",
        icon="mdi:trending-up",
        value_fn=lambda d: (d.latest_glucose or {}).get("trend"),
        attrs_fn=lambda d: {
            "arrow": TREND_ARROWS.get((d.latest_glucose or {}).get("trend"), "")
        },
    ),
    LoopSensorDescription(
        key="insulin_on_board",
        translation_key="insulin_on_board",
        native_unit_of_measurement="U",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:needle",
        value_fn=lambda d: _decision(d, "insulin_on_board"),
    ),
    LoopSensorDescription(
        key="carbs_on_board",
        translation_key="carbs_on_board",
        native_unit_of_measurement="g",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:food-apple",
        value_fn=lambda d: _decision(d, "carbs_on_board"),
    ),
    LoopSensorDescription(
        key="eventual_glucose",
        translation_key="eventual_glucose",
        native_unit_of_measurement="mg/dL",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:chart-line",
        value_fn=lambda d: _decision(d, "eventual_glucose_mgdl"),
    ),
    LoopSensorDescription(
        key="basal_rate",
        translation_key="basal_rate",
        native_unit_of_measurement="U/h",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:chart-timeline-variant",
        value_fn=lambda d: _status(d, "basal_rate"),
    ),
    LoopSensorDescription(
        key="pump_reservoir",
        translation_key="pump_reservoir",
        native_unit_of_measurement="U",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:gauge",
        value_fn=lambda d: _status(d, "reservoir_units"),
    ),
    LoopSensorDescription(
        key="pump_battery",
        translation_key="pump_battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _status(d, "pump_battery_percent"),
    ),
    LoopSensorDescription(
        key="last_loop_completed",
        translation_key="last_loop_completed",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _parse_dt(_status(d, "last_loop_completed")),
    ),
    LoopSensorDescription(
        key="last_carb_entry",
        translation_key="last_carb_entry",
        native_unit_of_measurement="g",
        icon="mdi:silverware-fork-knife",
        value_fn=lambda d: (d.last_carb_entry or {}).get("grams"),
        attrs_fn=lambda d: {
            "date": (d.last_carb_entry or {}).get("date"),
            "absorption_time_minutes": (d.last_carb_entry or {}).get(
                "absorption_time_minutes"
            ),
        },
    ),
    LoopSensorDescription(
        key="last_bolus",
        translation_key="last_bolus",
        native_unit_of_measurement="U",
        icon="mdi:needle",
        value_fn=lambda d: (d.last_bolus or {}).get("delivered_units")
        or (d.last_bolus or {}).get("programmed_units"),
        attrs_fn=lambda d: {
            "start_date": (d.last_bolus or {}).get("start_date"),
            "automatic": (d.last_bolus or {}).get("automatic"),
        },
    ),
    LoopSensorDescription(
        key="active_override",
        translation_key="active_override",
        icon="mdi:account-cog",
        value_fn=lambda d: (d.override or {}).get("name") if d.override else "none",
        attrs_fn=lambda d: d.override or {},
    ),
    LoopSensorDescription(
        key="last_alert",
        translation_key="last_alert",
        icon="mdi:alert",
        value_fn=lambda d: (d.last_alert or {}).get("title")
        or (d.last_alert or {}).get("alert_identifier"),
        attrs_fn=lambda d: d.last_alert or {},
    ),
    LoopSensorDescription(
        key="last_site_change",
        translation_key="last_site_change",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:pipe",
        value_fn=lambda d: _parse_dt(_status(d, "last_site_change")),
    ),
    LoopSensorDescription(
        key="last_reservoir_change",
        translation_key="last_reservoir_change",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:water-sync",
        value_fn=lambda d: _parse_dt(_status(d, "last_reservoir_change")),
    ),
    LoopSensorDescription(
        key="last_sensor_start",
        translation_key="last_sensor_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:leak",
        value_fn=lambda d: _parse_dt(_status(d, "last_sensor_start")),
    ),
    LoopSensorDescription(
        key="scheduled_basal_rate",
        translation_key="scheduled_basal_rate",
        native_unit_of_measurement="U/h",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        icon="mdi:chart-timeline-variant-shimmer",
        value_fn=lambda d: _current_schedule_value(d, "basal_schedule", "rate"),
        attrs_fn=lambda d: {"schedule": _settings(d, "basal_schedule")},
    ),
    LoopSensorDescription(
        key="carb_ratio",
        translation_key="carb_ratio",
        native_unit_of_measurement="g/U",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:division",
        value_fn=lambda d: _current_schedule_value(d, "carb_ratio_schedule", "ratio"),
        attrs_fn=lambda d: {"schedule": _settings(d, "carb_ratio_schedule")},
    ),
    LoopSensorDescription(
        key="insulin_sensitivity",
        translation_key="insulin_sensitivity",
        native_unit_of_measurement="mg/dL/U",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:diabetes",
        value_fn=lambda d: _current_schedule_value(
            d, "insulin_sensitivity_schedule", "sensitivity_mgdl"
        ),
        attrs_fn=lambda d: {"schedule": _settings(d, "insulin_sensitivity_schedule")},
    ),
    LoopSensorDescription(
        key="correction_range",
        translation_key="correction_range",
        icon="mdi:target",
        value_fn=lambda d: _correction_range_text(d),
        attrs_fn=lambda d: {
            "lower_mgdl": _current_schedule_value(
                d, "correction_range_schedule", "lower_mgdl"
            ),
            "upper_mgdl": _current_schedule_value(
                d, "correction_range_schedule", "upper_mgdl"
            ),
            "schedule": _settings(d, "correction_range_schedule"),
            "pre_meal_lower_mgdl": _settings(d, "pre_meal_lower_mgdl"),
            "pre_meal_upper_mgdl": _settings(d, "pre_meal_upper_mgdl"),
        },
    ),
    LoopSensorDescription(
        key="max_bolus",
        translation_key="max_bolus",
        native_unit_of_measurement="U",
        icon="mdi:arrow-up-bold",
        value_fn=lambda d: _settings(d, "maximum_bolus"),
    ),
    LoopSensorDescription(
        key="max_basal_rate",
        translation_key="max_basal_rate",
        native_unit_of_measurement="U/h",
        icon="mdi:arrow-up-bold-outline",
        value_fn=lambda d: _settings(d, "maximum_basal_rate"),
        attrs_fn=lambda d: {
            "suspend_threshold_mgdl": _settings(d, "suspend_threshold_mgdl"),
            "insulin_type": _settings(d, "insulin_type"),
        },
    ),
)


def _correction_range_text(data: LoopData) -> str | None:
    lower = _current_schedule_value(data, "correction_range_schedule", "lower_mgdl")
    upper = _current_schedule_value(data, "correction_range_schedule", "upper_mgdl")
    if lower is None or upper is None:
        return None
    return f"{lower:g}-{upper:g}"


def _parse_dt(value: str | None):
    return dt_util.parse_datetime(value) if value else None


def _current_schedule_value(data: LoopData, schedule_key: str, field: str):
    """Return the currently-active entry's value from a daily schedule.

    Schedule items are [{"start_minutes": int, ...}] sorted by start time;
    the active entry is the last one whose start has passed today.
    """
    items = (data.settings or {}).get(schedule_key) or []
    if not items:
        return None
    now = dt_util.now()
    now_minutes = now.hour * 60 + now.minute
    current = items[-1]  # wraps: before the first start, yesterday's last applies
    for item in items:
        if item.get("start_minutes", 0) <= now_minutes:
            current = item
    return current.get(field)


def _settings(data: LoopData, key: str):
    return (data.settings or {}).get(key)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Loop sensors."""
    data: LoopData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(LoopSensor(entry, data, desc) for desc in SENSORS)


class LoopSensor(SensorEntity):
    """A sensor fed by pushed Loop data."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: LoopSensorDescription

    def __init__(
        self, entry: ConfigEntry, data: LoopData, description: LoopSensorDescription
    ) -> None:
        self.entity_description = description
        self._data = data
        self._entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title or "Loop",
            manufacturer="LoopKit",
            model="AID app (HomeAssistantService)",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_update(self._entry_id), self._handle_update
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self._data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self._data)
