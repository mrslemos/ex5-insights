"""Fields to type what the car cannot know: the amount paid and the station's kWh of the latest paid charge.

They work on any phone (the notification's text field is iPhone only) and are unavailable when nothing is pending.
"""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfEnergy

from .entity import Ex5Entity


async def async_setup_entry(hass, entry, add) -> None:
    t = entry.runtime_data
    add([PendingCost(t), PendingStationKwh(t)])


class PendingCost(Ex5Entity, NumberEntity):
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 100000
    _attr_native_step = 0.01
    _attr_device_class = NumberDeviceClass.MONETARY
    _attr_icon = "mdi:cash-edit"

    def __init__(self, tracker) -> None:
        super().__init__(tracker, "pending_cost", "number")
        self._attr_native_unit_of_measurement = tracker.currency

    @property
    def available(self) -> bool:
        return self.tracker.pending_cost() is not None

    @property
    def native_value(self):
        return None

    @property
    def extra_state_attributes(self):
        c = self.tracker.pending_cost()
        return {"charge_id": c["id"], "kwh": c.get("kwh"), "place": c.get("place")} if c else None

    async def async_set_native_value(self, value: float) -> None:
        self.tracker.set_cost(value)


class PendingStationKwh(Ex5Entity, NumberEntity):
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0.5
    _attr_native_max_value = 200
    _attr_native_step = 0.01
    _attr_device_class = NumberDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, tracker) -> None:
        super().__init__(tracker, "pending_station_kwh", "number")

    @property
    def available(self) -> bool:
        return self.tracker.pending_station_kwh() is not None

    @property
    def native_value(self):
        return None

    @property
    def extra_state_attributes(self):
        c = self.tracker.pending_station_kwh()
        return {"charge_id": c["id"], "measured_kwh": c.get("kwh"), "place": c.get("place")} if c else None

    async def async_set_native_value(self, value: float) -> None:
        self.tracker.set_station_kwh(value)
