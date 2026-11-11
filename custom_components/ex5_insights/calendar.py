"""The trips as a calendar: one event per trip (origin → destination · km), with times, battery and the map link."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

from .entity import Ex5Entity


async def async_setup_entry(hass, entry, add) -> None:
    add([TripsCalendar(entry.runtime_data)])


class TripsCalendar(Ex5Entity, CalendarEntity):
    _attr_icon = "mdi:car-clock"

    def __init__(self, tracker) -> None:
        super().__init__(tracker, "trips", "calendar")

    def _event(self, t: dict) -> CalendarEvent:
        start = dt_util.utc_from_timestamp(t["start"])
        end = dt_util.utc_from_timestamp(max(t["end"], t["start"] + 60))
        return CalendarEvent(start=start, end=end, summary=self.tracker.trip_summary(t),
                             description=self.tracker.trip_description(t), uid=f"ex5_trip_{t.get('id')}")

    @property
    def event(self) -> CalendarEvent | None:
        ts = self.tracker.trips
        return self._event(max(ts, key=lambda x: x["start"])) if ts else None

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        a, b = start_date.timestamp(), end_date.timestamp()
        return [self._event(t) for t in sorted(self.tracker.trips, key=lambda x: x["start"])
                if t["end"] >= a and t["start"] < b]
