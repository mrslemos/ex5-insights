"""What the EX5 cards read from Home Assistant (signed-in users only): the cards' script, the car pictures, and the
trips of a day with their paths for the timeline card."""
from __future__ import annotations

import os
import re

from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import DOMAIN, FRONTEND_URL

HERE = os.path.dirname(os.path.abspath(__file__))
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _tracker(hass: HomeAssistant, entry_id: str | None):
    entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED]
    if entry_id:
        entries = [e for e in entries if e.entry_id == entry_id]
    entries.sort(key=lambda e: e.entry_id)
    return entries[0].runtime_data if entries else None


class DaysView(HomeAssistantView):
    url = "/api/ex5_insights/days"
    name = "api:ex5_insights:days"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        t = _tracker(self.hass, request.query.get("entry"))
        return self.json(t.trip_days() if t else [])


class DayView(HomeAssistantView):
    url = "/api/ex5_insights/day/{day}"
    name = "api:ex5_insights:day"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request, day):
        if not DAY.match(day):
            return self.json_message("invalid day", 400)
        t = _tracker(self.hass, request.query.get("entry"))
        if t is None:
            return self.json([])
        return self.json(await self.hass.async_add_executor_job(t.trip_day, day))


async def async_register(hass: HomeAssistant) -> None:
    """Once per Home Assistant start: static files, the API and the cards' script on every page."""
    if hass.data.get(f"{DOMAIN}_http"):
        return
    hass.data[f"{DOMAIN}_http"] = True
    await hass.http.async_register_static_paths([
        StaticPathConfig(f"{FRONTEND_URL}/images", os.path.join(HERE, "images"), True),
        StaticPathConfig(f"{FRONTEND_URL}/frontend", os.path.join(HERE, "frontend"), False),
    ])
    hass.http.register_view(DaysView(hass))
    hass.http.register_view(DayView(hass))
    from homeassistant.components.frontend import add_extra_js_url
    from .const import VERSION
    add_extra_js_url(hass, f"{FRONTEND_URL}/frontend/ex5-insights-cards.js?v={VERSION}")
