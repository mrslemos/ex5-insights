"""Month shown by the month sensors and the charge table (this month and every earlier month with data)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity

from .entity import Ex5Entity


async def async_setup_entry(hass, entry, add) -> None:
    add([MonthSelect(entry.runtime_data)])


class MonthSelect(Ex5Entity, SelectEntity):
    _attr_icon = "mdi:calendar-month"

    def __init__(self, tracker) -> None:
        super().__init__(tracker, "month", "select")

    def _label(self, month: str) -> str:
        return self.tracker.t("this_month") if month == self.tracker.current_month else self.tracker.month_label(month)

    @property
    def options(self) -> list[str]:
        return [self._label(m) for m in self.tracker.month_options()]

    @property
    def current_option(self) -> str:
        return self._label(self.tracker.selected_month)

    async def async_select_option(self, option: str) -> None:
        for m in self.tracker.month_options():
            if self._label(m) == option:
                self.tracker.select_month(m)
                return
