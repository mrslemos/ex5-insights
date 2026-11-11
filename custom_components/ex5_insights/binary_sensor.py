"""Charge and trip in progress."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .entity import Ex5Entity


async def async_setup_entry(hass, entry, add) -> None:
    add([Charging(entry.runtime_data), Driving(entry.runtime_data)])


class Charging(Ex5Entity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, tracker) -> None:
        super().__init__(tracker, "charging", "binary_sensor")

    @property
    def is_on(self) -> bool:
        return self.tracker.session is not None

    @property
    def extra_state_attributes(self):
        s = self.tracker.session
        return {"kind": s.kind} if s else None


class Driving(Ex5Entity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.MOVING

    def __init__(self, tracker) -> None:
        super().__init__(tracker, "driving", "binary_sensor")

    @property
    def is_on(self) -> bool:
        return self.tracker.driving

    @property
    def extra_state_attributes(self):
        trip = self.tracker.data.get("trip")
        if not trip:
            stop = self.tracker.data.get("stop") or {}
            return {"parked_at": stop.get("place")} if stop else None
        return {"started": trip["start"], "battery_start": trip.get("battery_start"), "points": len(trip["points"])}
