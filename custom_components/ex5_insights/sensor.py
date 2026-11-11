"""Sensors: the chosen month (km, charges, kWh, cost, consumption, cost per km, the charge table) and the last
charge. The month follows select.ex5_month."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import KEY_BATTERY, KEY_ODOMETER, KEY_RANGE, PAINT, DARK_PAINT, FRONTEND_URL
from .entity import Ex5Entity
from .image import color_file


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
        RealRange(t, "real_range", "all", "mdi:map-marker-distance"),
        RealRange(t, "real_range_highway", "highway", "mdi:highway"),
        RealRange(t, "real_range_city", "city", "mdi:city-variant-outline"),
        RangeNow(t, "range_now", "all", "mdi:map-marker-distance"),
        RangeNow(t, "range_now_highway", "highway", "mdi:highway"),
        RangeNow(t, "range_now_city", "city", "mdi:city-variant-outline"),
        CarRangeFull(t),
        Mirror(t, "car_range", KEY_RANGE, UnitOfLength.KILOMETERS, SensorDeviceClass.DISTANCE, None, "mdi:car-info"),
        Battery(t),
        Mirror(t, "odometer", KEY_ODOMETER, UnitOfLength.KILOMETERS, SensorDeviceClass.DISTANCE,
               SensorStateClass.TOTAL_INCREASING, "mdi:counter"),
        BatteryCapacity(t),
        BatteryHealth(t),
        LastTrip(t),
        MonthTrips(t),
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


class RealRange(Ex5Entity, SensorEntity):
    """km per 100 % of battery actually used, looking back over the latest trips (all, highway or city)."""

    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, tracker, key, kind, icon) -> None:
        super().__init__(tracker, key, "sensor")
        self._kind = kind
        self._attr_icon = icon

    @property
    def available(self) -> bool:
        return self.tracker.real_range()[self._kind]["km_per_charge"] is not None

    @property
    def native_value(self):
        return self.tracker.real_range()[self._kind]["km_per_charge"]

    @property
    def extra_state_attributes(self):
        r = self.tracker.real_range()[self._kind]
        return {k: r.get(k) for k in ("preview", "km", "battery_pct", "trips", "kwh_100km", "parked_pct") if k in r}


class RangeNow(Ex5Entity, SensorEntity):
    """How far the current battery goes at the measured pace (real range × battery ÷ 100)."""

    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_suggested_display_precision = 0

    def __init__(self, tracker, key, kind, icon) -> None:
        super().__init__(tracker, key, "sensor")
        self._kind = kind
        self._attr_icon = icon

    @property
    def available(self) -> bool:
        return self.tracker.real_range()[self._kind]["range_now"] is not None

    @property
    def native_value(self):
        return self.tracker.real_range()[self._kind]["range_now"]


class CarRangeFull(Ex5Entity, SensorEntity):
    """The car's own range estimate taken to a full battery."""

    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:car-info"
    _attr_suggested_display_precision = 0

    def __init__(self, tracker) -> None:
        super().__init__(tracker, "car_range_full", "sensor")

    @property
    def available(self) -> bool:
        return self.tracker.car_range_full() is not None

    @property
    def native_value(self):
        return self.tracker.car_range_full()


class Mirror(Ex5Entity, SensorEntity):
    """A Geely Connect value under a fixed EX5 Insights entity id, so the ready-made dashboard works for any car."""

    def __init__(self, tracker, key, source, unit, device_class, state_class, icon, decimals=0) -> None:
        super().__init__(tracker, key, "sensor")
        self._source = source
        self._attr_suggested_display_precision = decimals
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_icon = icon

    @property
    def available(self) -> bool:
        return self.tracker.car_value(self._source) is not None

    @property
    def native_value(self):
        return self.tracker.car_value(self._source)


class Battery(Mirror):
    """Battery level; its attributes tell the EX5 cards which Geely Connect car and picture to show."""

    _unrecorded_attributes = frozenset({"geely_prefix", "tracker", "car_image", "paint", "dark_paint"})

    def __init__(self, tracker) -> None:
        super().__init__(tracker, "battery", KEY_BATTERY, PERCENTAGE, SensorDeviceClass.BATTERY, None, None)
        self._image = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        path = await self.hass.async_add_executor_job(color_file, self.tracker.color)
        if path:
            import os
            self._image = f"{FRONTEND_URL}/images/{os.path.basename(path)}"

    @property
    def extra_state_attributes(self):
        color = self.tracker.color
        return {"geely_prefix": self.tracker.geely_prefix, "tracker": self.tracker.tracker_entity,
                "car_image": self._image, "paint": PAINT.get(color or ""), "dark_paint": color in DARK_PAINT}


class BatteryCapacity(Ex5Entity, SensorEntity):
    """Real capacity measured in the charges (average of the latest three, times the calibration factor)."""

    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY_STORAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:battery-high"

    def __init__(self, tracker) -> None:
        super().__init__(tracker, "battery_capacity", "sensor")

    @property
    def available(self) -> bool:
        return self.tracker.measured_capacity is not None

    @property
    def native_value(self):
        return self.tracker.measured_capacity

    @property
    def extra_state_attributes(self):
        ms = self.tracker.data.get("capacity_measurements", [])
        return {"published_kwh": self.tracker.nominal_capacity, "measurements": len(ms),
                "latest": ms[-1] if ms else None}


class BatteryHealth(Ex5Entity, SensorEntity):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:battery-heart"

    def __init__(self, tracker) -> None:
        super().__init__(tracker, "battery_health", "sensor")

    @property
    def available(self) -> bool:
        return self.tracker.health is not None

    @property
    def native_value(self):
        return self.tracker.health


class LastTrip(Ex5Entity, SensorEntity):
    _attr_icon = "mdi:car-arrow-right"
    _unrecorded_attributes = frozenset({"trip"})

    def __init__(self, tracker) -> None:
        super().__init__(tracker, "last_trip", "sensor")

    @property
    def native_value(self):
        return self.tracker.last_trip_text()

    @property
    def extra_state_attributes(self):
        ts = self.tracker.trips
        if not ts:
            return None
        t = max(ts, key=lambda x: x["start"])
        return {"trip": {k: v for k, v in t.items() if "itude" not in k}}


class MonthTrips(Ex5Entity, SensorEntity):
    """State = trips in the chosen month; attribute "trips" feeds the dashboard list (day, time, summary, map)."""

    _attr_icon = "mdi:format-list-bulleted"
    _unrecorded_attributes = frozenset({"trips"})

    def __init__(self, tracker) -> None:
        super().__init__(tracker, "month_trips", "sensor")

    @property
    def native_value(self):
        return len(self.tracker.month_trips())

    @property
    def extra_state_attributes(self):
        m = self.tracker.selected_month
        return {"month": m, "month_label": self.tracker.month_label(m), "trips": self.tracker.month_trips(m)}
