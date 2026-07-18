"""Binary sensors for the Loop integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LoopData
from .const import DOMAIN, signal_update


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Loop binary sensors."""
    data: LoopData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            LoopBinarySensor(entry, data, "closed_loop", "closed_loop"),
            LoopBinarySensor(
                entry,
                data,
                "pump_suspended",
                "pump_suspended",
                device_class=BinarySensorDeviceClass.PROBLEM,
            ),
        ]
    )


class LoopBinarySensor(BinarySensorEntity):
    """Binary sensor fed by pushed Loop status."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: ConfigEntry,
        data: LoopData,
        key: str,
        translation_key: str,
        device_class: BinarySensorDeviceClass | None = None,
    ) -> None:
        self._data = data
        self._key = key
        self._entry_id = entry.entry_id
        self._attr_translation_key = translation_key
        self._attr_device_class = device_class
        self._attr_unique_id = f"{entry.entry_id}_{key}"
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
    def is_on(self) -> bool | None:
        value = (self._data.status or {}).get(self._key)
        return bool(value) if value is not None else None
