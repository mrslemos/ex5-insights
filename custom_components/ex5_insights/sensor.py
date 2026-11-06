"""Sensors: the chosen month (km, charges, kWh, cost, consumption, cost per km, the charge table) and the last
charge. The month follows select.ex5_month."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import UnitOfEnergy, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import Ex5Entity


async def async_setup_entry(hass: HomeAssistant, entry, add: AddEntitiesCallback) -> None:
    t = entry.runtime_data
    add([
        MonthSensor(t, "month_distance", "distance", UnitOfLength.KILOMETERS, SensorDeviceClass.DISTANCE, 0),
        MonthSensor(t, "month_charges", "charges", None, None, 0, attrs=("charges_ac", "charges_dc")),
        MonthSensor(t, "month_energy", "kwh", UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, 1,
                    attrs=("kwh_ac", "kwh_dc")),
        MonthSensor(t, "month_cost", "cost", "currency", SensorDeviceClass.MONETARY, 2, attrs=("pending",)),
        MonthSensor(t, "month_consumption", "consumption", "kWh/100 km", None, 1),
        MonthSensor(t, "month_cost_per_km", "cost_per_km", "currency/km", None, 2),
        MonthTable(t),
        LastCharge(t),
        SessionEnergy(t),
    ])


class MonthSensor(Ex5Entity, SensorEntity):
    def __init__(self, tracker, key, field, unit, device_class, decimals, attrs=()) -> None:
        super().__init__(tracker, key, "sensor")
        self._field, self._attrs = field, attrs
        if unit == "currency":
            unit = tracker.currency  # "BRL" makes the frontend show "R$ 60,58"
        elif unit == "currency/km":
            unit = f"{tracker.currency}/km"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_suggested_display_precision = decimals

    @property
    def native_value(self):
        return self.tracker.summary()[self._field]

    @property
    def extra_state_attributes(self):
        s = self.tracker.summary()
        out = {"month": s["month"], "month_label": self.tracker.month_label(s["month"])}
        out.update({a: s[a] for a in self._attrs})
        return out


class MonthTable(Ex5Entity, SensorEntity):
    """State = number of charges in the month; attributes "rows" and "total" feed the dashboard table."""

    _unrecorded_attributes = frozenset({"rows", "total"})
    _attr_icon = "mdi:format-list-bulleted"

    def __init__(self, tracker) -> None:
        super().__init__(tracker, "month_table", "sensor")

    @property
    def native_value(self):
        return self.tracker.summary()["charges"]

    @property
    def extra_state_attributes(self):
        s = self.tracker.summary()
        return {"month": s["month"], "month_label": self.tracker.month_label(s["month"]), "rows": s["rows"],
                "total": {**s["total_row"], "pending": s["pending"]}}


class LastCharge(Ex5Entity, SensorEntity):
    _attr_icon = "mdi:ev-station"
    _unrecorded_attributes = frozenset({"charge"})

    def __init__(self, tracker) -> None:
        super().__init__(tracker, "last_charge", "sensor")

    @property
    def native_value(self):
        return self.tracker.last_charge_text()

    @property
    def extra_state_attributes(self):
        c = self.tracker.last_charge()
        if not c:
            return None
        hidden = {"latitude", "longitude"}  # the place name is enough; coordinates stay in storage only
        return {"charge": {k: v for k, v in c.items() if k not in hidden}}


class SessionEnergy(Ex5Entity, SensorEntity):
    """Energy of the charge in progress (unavailable when not charging)."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2

    def __init__(self, tracker) -> None:
        super().__init__(tracker, "session_energy", "sensor")

    @property
    def available(self) -> bool:
        return self.tracker.session is not None

    @property
    def native_value(self):
        s = self.tracker.session
        return round(s.energy + s.gaps, 3) if s else None

    @property
    def extra_state_attributes(self):
        s = self.tracker.session
        if not s:
            return None
        return {"kind": s.kind, "battery_start": s.battery_start, "started": s.start}
