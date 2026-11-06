"""Base entity: one EX5 device, refreshed whenever the tracker changes."""
from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import CONF_DEVICE, DOMAIN, SIGNAL_UPDATE
from .tracker import Ex5Tracker


class Ex5Entity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, tracker: Ex5Tracker, key: str, platform: str) -> None:
        self.tracker = tracker
        self._attr_translation_key = key
        self._attr_unique_id = f"{tracker.entry.entry_id}_{key}"
        # Fixed English entity ids (sensor.ex5_month_cost...) so the ready-made dashboards work in any language.
        suffix = "" if tracker.is_first_entry else f"_{tracker.short}"
        self.entity_id = f"{platform}.ex5_{key}{suffix}"
        via = None
        dev = dr.async_get(tracker.hass).async_get(tracker.entry.data[CONF_DEVICE])
        if dev and dev.identifiers:
            via = next(iter(dev.identifiers))
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tracker.entry.entry_id)},
            name="EX5",
            manufacturer="EX5 Insights",
            model="Geely EX5",
            via_device=via,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE.format(self.tracker.entry.entry_id), self._refresh))

    def _refresh(self) -> None:
        self.async_write_ha_state()
