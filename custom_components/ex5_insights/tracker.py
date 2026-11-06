"""The part of EX5 Insights that talks to Home Assistant: follows the car, records charges, keeps the diary."""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import core
from .const import (
    ACTION_COST, ACTION_KWH, CHARGING_STATE, CONF_CAPACITY, CONF_DEVICE, CONF_END_MINUTES, CONF_NOTIFY, CONF_PLACES,
    DEFAULT_CAPACITY, DEFAULT_END_MINUTES, DOMAIN, EVENT_CHARGE_FINISHED, KEY_BATTERY, KEY_CHARGER, KEY_ODOMETER,
    KEY_POWER, KEY_RANGE, KEY_REPORTED, KEY_TRACKER, MONTHS, REQUIRED_KEYS, SIGNAL_UPDATE, SOURCE_DOMAIN,
    SOURCE_KEYS, STORAGE_VERSION, TEXTS, lang_key,
)

_LOGGER = logging.getLogger(__name__)
_BAD = (None, "", STATE_UNKNOWN, STATE_UNAVAILABLE)


def resolve_entities(hass: HomeAssistant, device_id: str) -> dict[str, str]:
    """Entity ids of the Geely Connect device, by key (unique ids are "geely_<VIN>_<key>")."""
    reg = er.async_get(hass)
    found: dict[str, str] = {}
    for e in er.async_entries_for_device(reg, device_id):
        if e.platform != SOURCE_DOMAIN or not e.unique_id:
            continue
        parts = e.unique_id.split("_", 2)
        if len(parts) == 3 and parts[0] == "geely":
            found.setdefault(parts[2], e.entity_id)
    return {k: found[k] for k in SOURCE_KEYS if k in found}


def _float(state: State | None, attr: str | None = None) -> float | None:
    if state is None:
        return None
    value = state.attributes.get(attr) if attr else state.state
    if value in _BAD:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class Ex5Tracker:
    """One car. Data lives in .storage/ex5_insights.<entry_id>."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.short = entry.entry_id[:8]
        self.entities = resolve_entities(hass, entry.data[CONF_DEVICE])
        missing = [k for k in REQUIRED_KEYS if k not in self.entities]
        if missing:
            raise HomeAssistantError(f"Geely Connect entities not found: {', '.join(missing)}")
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.data: dict[str, Any] = {}
        self.session: core.ChargeSession | None = None
        self._idle_since: float | None = None
        self._unsubs: list = []
        self._stats_timer = None

    # ------------------------------------------------------------ settings

    @property
    def options(self) -> dict:
        return {**self.entry.data, **self.entry.options}

    @property
    def capacity(self) -> float:
        return float(self.options.get(CONF_CAPACITY) or DEFAULT_CAPACITY)

    @property
    def places(self) -> list[core.Place]:
        return [core.Place.from_dict(p) for p in self.options.get(CONF_PLACES, [])]

    @property
    def lang(self) -> str:
        return lang_key(self.hass.config.language)

    @property
    def language(self) -> str:
        return self.hass.config.language or "en"

    def t(self, key: str, **kw) -> str:
        return TEXTS[self.lang][key].format(**kw)

    @property
    def currency(self) -> str:
        return self.hass.config.currency or "BRL"

    def money(self, value: float) -> str:
        symbol = {"BRL": "R$", "USD": "$", "EUR": "€"}.get(self.currency, self.currency)
        return f"{symbol} {core.fmt_number(value, 2, self.language)}"

    # ------------------------------------------------------------ start / stop

    async def async_start(self) -> None:
        stored = await self._store.async_load() or {}
        self.data = {
            "charges": stored.get("charges", []),
            "last_report": stored.get("last_report", {}),
            "odometer_marks": stored.get("odometer_marks", {}),
            "distance_overrides": stored.get("distance_overrides", {}),
            "totals": stored.get("totals", {"AC": 0.0, "DC": 0.0, "cost": 0.0}),
            "next_id": stored.get("next_id", 1),
            "selected_month": stored.get("selected_month"),
        }
        if stored.get("session"):
            self.session = core.ChargeSession.from_dict(stored["session"])
            self._resume_after_restart()
        watch = [self.entities[k] for k in (KEY_POWER, KEY_CHARGER, KEY_BATTERY, KEY_ODOMETER, KEY_REPORTED)
                 if k in self.entities]
        self._unsubs.append(async_track_state_change_event(self.hass, watch, self._on_change))
        self._unsubs.append(async_track_time_interval(self.hass, self._on_tick, timedelta(seconds=60)))
        self._unsubs.append(self.hass.bus.async_listen("mobile_app_notification_action", self._on_notification))
        self._mark_odometer()
        self._evaluate(dt_util.utcnow().timestamp())
        self._schedule_statistics()

    async def async_stop(self) -> None:
        for u in self._unsubs:
            u()
        self._unsubs.clear()
        if self._stats_timer:
            self._stats_timer()
        if self.session:
            self.session.advance(dt_util.utcnow().timestamp())
        await self._store.async_save(self._snapshot())

    def _snapshot(self) -> dict:
        return {**self.data, "session": self.session.to_dict() if self.session else None}

    def _save(self, now: bool = False) -> None:
        if now:
            self.hass.async_create_task(self._store.async_save(self._snapshot()))
        else:
            self._store.async_delay_save(self._snapshot, 30)

    def _notify_entities(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_UPDATE.format(self.entry.entry_id))

    # ------------------------------------------------------------ reading the car

    def _state(self, key: str) -> State | None:
        eid = self.entities.get(key)
        return self.hass.states.get(eid) if eid else None

    def _power(self) -> tuple[float, str | None]:
        s = self._state(KEY_POWER)
        return (_float(s) or 0.0), (s.attributes.get("supply") if s else None)

    def _battery(self) -> float | None:
        return _float(self._state(KEY_BATTERY))

    def _charging_now(self) -> bool:
        charger = self._state(KEY_CHARGER)
        power, _ = self._power()
        return (charger is not None and charger.state == CHARGING_STATE) or power > core.POWER_ON_KW

    def _idle_now(self) -> bool:
        charger = self._state(KEY_CHARGER)
        power, _ = self._power()
        return (charger is None or charger.state != CHARGING_STATE) and power < 0.1

    def _position(self) -> tuple[float | None, float | None]:
        s = self._state(KEY_TRACKER)
        return (_float(s, "latitude"), _float(s, "longitude")) if s else (None, None)

    # ------------------------------------------------------------ events

    @callback
    def _on_change(self, event: Event) -> None:
        now = dt_util.utcnow().timestamp()
        eid = event.data["entity_id"]
        new: State | None = event.data.get("new_state")
        if eid == self.entities.get(KEY_ODOMETER):
            self._mark_odometer()
            return
        if self.session:
            if eid == self.entities.get(KEY_POWER) and new is not None:
                power = _float(new) or 0.0
                self.session.add_power(now, power, new.attributes.get("supply"), self.capacity)
            elif eid == self.entities.get(KEY_BATTERY) and new is not None:
                b = _float(new)
                if b is not None:
                    self.session.add_battery(now, b)
        self._evaluate(now)
        if eid in (self.entities.get(KEY_BATTERY), self.entities.get(KEY_REPORTED)) and not self.session:
            b = self._battery()
            if b is not None:
                self.data["last_report"] = {"battery": b, "time": now}
                self._save()

    @callback
    def _on_tick(self, _now: datetime) -> None:
        now = dt_util.utcnow().timestamp()
        if self.session:
            self.session.advance(now)
            self._save()
        self._mark_odometer()
        self._evaluate(now)
        self._notify_entities()

    def _evaluate(self, now: float) -> None:
        if self.session is None:
            if self._charging_now():
                self._start_session(now)
            return
        if self._idle_now():
            if self._idle_since is None:
                self._idle_since = now
            end_after = 60 * float(self.options.get(CONF_END_MINUTES, DEFAULT_END_MINUTES))
            if now - self._idle_since >= end_after:
                self._finish_session(self._idle_since)
        else:
            self._idle_since = None

    # ------------------------------------------------------------ sessions

    def _start_session(self, now: float) -> None:
        power, supply = self._power()
        battery = self._battery()
        odo = _float(self._state(KEY_ODOMETER))
        lat, lon = self._position()
        s = core.ChargeSession(start=now, battery_start=battery if battery is not None else 0.0, odometer=odo,
                               latitude=lat, longitude=lon, power_time=now)
        # Silent start: the car often reports a charge only minutes after it began, with the battery already up.
        # The stretch since the previous report is estimated from the battery rise and the start moved back.
        last = self.data.get("last_report") or {}
        if battery is not None and last.get("battery") is not None and power > core.POWER_ON_KW:
            added = s.fill_gap(float(last["time"]), now, 0.0, power, float(last["battery"]), battery, self.capacity)
            if added > 0:
                s.battery_start = float(last["battery"])
                s.start = max(now - added / power * 3600, float(last["time"]))
        s.add_power(now, power, supply, self.capacity)
        if battery is not None:
            s.add_battery(now, battery)
        self.session = s
        self._idle_since = None
        _LOGGER.debug("Charge started: %s", s)
        self._save(now=True)
        self._notify_entities()

    def _resume_after_restart(self) -> None:
        """HA was off during a charge: fill the stretch without readings, then carry on."""
        s = self.session
        now = dt_util.utcnow().timestamp()
        power, supply = self._power()
        battery = self._battery()
        s.fill_gap(s.power_time, now, s.power, power, s.battery, battery, self.capacity)
        s.power_time, s.power = now, power
        if battery is not None:
            s.add_battery(now, battery)
        if self._idle_now():
            charger = self._state(KEY_CHARGER)
            ended = charger.last_changed.timestamp() if charger is not None else now
            self._idle_since = max(min(ended, now), s.start)

    def _finish_session(self, end: float) -> None:
        s = self.session
        self.session, self._idle_since = None, None
        result = s.result(end, self._battery(), self.capacity)
        if result["battery_end"] is not None:
            self.data["last_report"] = {"battery": result["battery_end"], "time": end}
        if not result.pop("valid"):
            _LOGGER.debug("Charge too small, ignored: %s", result)
            self._save(now=True)
            self._notify_entities()
            return
        place = core.find_place(self.places, s.latitude, s.longitude)
        if place:
            name = place.name
            rule, tariff = place.rule_for(result["kind"])
        else:
            name, rule, tariff = self._place_name(), core.RULE_ASK, 0.0
        cost = core.charge_cost(result["kwh"], rule, tariff)
        charge = {**result, "id": self.data["next_id"], "place": name, "rule": rule, "tariff": tariff,
                  "cost": cost, "kwh_station": None, "date_only": False}
        self.data["next_id"] += 1
        self.data["charges"].append(charge)
        self.data["totals"][result["kind"]] += result["kwh"]
        if cost:
            self.data["totals"]["cost"] += cost
        self._save(now=True)
        self._notify_entities()
        self._schedule_statistics()
        self.hass.bus.async_fire(EVENT_CHARGE_FINISHED, {
            "entry_id": self.entry.entry_id, **{k: charge[k] for k in (
                "id", "kind", "place", "kwh", "cost", "minutes", "battery_start", "battery_end")},
        })
        self.hass.async_create_task(self._notify_finished(charge))

    def _place_name(self) -> str:
        tracker = self._state(KEY_TRACKER)
        if tracker is None or tracker.state in _BAD or tracker.state == "not_home":
            return self.t("unknown_place")
        if tracker.state == "home":
            return self.t("home")
        zone = self.hass.states.get(f"zone.{tracker.state}")
        return zone.name if zone else tracker.state

    # ------------------------------------------------------------ odometer, months

    def _mark_odometer(self) -> None:
        odo = _float(self._state(KEY_ODOMETER))
        if odo is None:
            return
        month = dt_util.now().strftime("%Y-%m")
        if month not in self.data["odometer_marks"]:
            self.data["odometer_marks"][month] = odo
            self._save()

    @property
    def current_month(self) -> str:
        return dt_util.now().strftime("%Y-%m")

    @property
    def selected_month(self) -> str:
        m = self.data.get("selected_month")
        return m if m and m < self.current_month else self.current_month

    def select_month(self, month: str) -> None:
        self.data["selected_month"] = None if month >= self.current_month else month
        self._save()
        self._notify_entities()

    def month_options(self) -> list[str]:
        tz = dt_util.get_default_time_zone()
        firsts = [core.month_key(c["start"], tz) for c in self.charges]
        firsts += list(self.data["odometer_marks"]) + list(self.data["distance_overrides"])
        first = min(firsts) if firsts else self.current_month
        return core.months_between(min(first, self.current_month), self.current_month)

    def month_label(self, month: str) -> str:
        y, m = month.split("-")
        return self.t("month_label", month=MONTHS[self.lang][int(m) - 1].capitalize(), year=y)

    @property
    def charges(self) -> list[dict]:
        return [c for c in self.data["charges"] if not c.get("deleted")]

    def summary(self, month: str | None = None) -> dict:
        month = month or self.selected_month
        tz = dt_util.get_default_time_zone()
        dist = core.month_distance(month, self.data["odometer_marks"], _float(self._state(KEY_ODOMETER)),
                                   self.data["distance_overrides"])
        return core.month_summary(self.charges, month, dist, self.language, tz)

    def last_charge(self) -> dict | None:
        live = [c for c in self.charges if not c.get("imported")]
        return max(live, key=lambda c: c["start"]) if live else None

    def pending_cost(self) -> dict | None:
        """The most recent charge still without a cost (in the last 60 days)."""
        limit = dt_util.utcnow().timestamp() - 60 * 86400
        cands = [c for c in self.charges if c.get("cost") is None and c["start"] >= limit]
        return max(cands, key=lambda c: c["start"]) if cands else None

    def pending_station_kwh(self) -> dict | None:
        """The most recent paid ("ask") charge still without the station's kWh (in the last 60 days)."""
        limit = dt_util.utcnow().timestamp() - 60 * 86400
        cands = [c for c in self.charges if c.get("rule") == core.RULE_ASK and c.get("kwh_station") is None
                 and not c.get("imported") and c["start"] >= limit]
        return max(cands, key=lambda c: c["start"]) if cands else None

    # ------------------------------------------------------------ user input

    def _find(self, charge_id: int | None, fallback) -> dict | None:
        if charge_id is None:
            return fallback()
        for c in self.data["charges"]:
            if c.get("id") == charge_id:
                return c
        return None

    def set_cost(self, value: float, charge_id: int | None = None) -> dict | None:
        c = self._find(charge_id, self.pending_cost)
        if c is None:
            return None
        old = c.get("cost") or 0.0
        c["cost"] = round(float(value), 2)
        if not c.get("imported"):
            self.data["totals"]["cost"] += c["cost"] - old
        self._changed()
        return c

    def set_station_kwh(self, value: float, charge_id: int | None = None) -> dict | None:
        """The station's kWh become the charge's official energy (it is what was paid for)."""
        c = self._find(charge_id, self.pending_station_kwh)
        if c is None:
            return None
        old = float(c.get("kwh") or 0)
        c["kwh_station"] = c["kwh"] = round(float(value), 2)
        if not c.get("imported"):
            self.data["totals"][c.get("kind", "AC")] += c["kwh"] - old
        self._changed()
        return c

    def set_month_distance(self, month: str, km: float | None) -> None:
        if km is None:
            self.data["distance_overrides"].pop(month, None)
        else:
            self.data["distance_overrides"][month] = float(km)
        self._changed()

    def delete_charge(self, charge_id: int, restore: bool = False) -> bool:
        for c in self.data["charges"]:
            if c.get("id") == charge_id:
                c["deleted"] = not restore
                self._changed()
                return True
        return False

    def import_charges(self, text: str) -> dict:
        """Adds charges from a CSV (see core.parse_charges_csv). Same day + same kWh = already there, skipped."""
        tz = dt_util.get_default_time_zone()
        rows, problems = core.parse_charges_csv(text, tz)
        have = {(datetime.fromtimestamp(c["start"], tz).date(), round(float(c.get("kwh") or 0), 1))
                for c in self.charges}
        added = 0
        for r in rows:
            key = (datetime.fromtimestamp(r["start"], tz).date(), round(r["kwh"], 1))
            if key in have:
                continue
            have.add(key)
            r["id"] = self.data["next_id"]
            r["rule"] = core.RULE_ASK if r["cost"] is None else core.RULE_FIXED
            self.data["next_id"] += 1
            self.data["charges"].append(r)
            added += 1
        if added:
            self._changed()
        return {"added": added, "skipped": len(rows) - added, "problems": problems}

    def export_csv(self) -> str:
        tz = dt_util.get_default_time_zone()
        cols = ["id", "start", "end", "type", "place", "battery_start", "battery_end", "kwh", "kwh_measured",
                "kwh_gaps", "kwh_battery", "kwh_station", "minutes", "odometer", "cost", "imported"]
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        for c in sorted(self.charges, key=lambda c: c["start"]):
            def when(x, date_only=False):
                if x is None:
                    return ""
                d = datetime.fromtimestamp(x, tz)
                return d.strftime("%Y-%m-%d") if date_only else d.isoformat(timespec="seconds")
            w.writerow([c.get("id"), when(c["start"], c.get("date_only")), when(c.get("end")), c.get("kind"),
                        c.get("place", ""), c.get("battery_start", ""), c.get("battery_end", ""), c.get("kwh"),
                        c.get("kwh_measured", ""), c.get("kwh_gaps", ""), c.get("kwh_battery", ""),
                        c.get("kwh_station") or "", c.get("minutes") or "", c.get("odometer") or "",
                        "" if c.get("cost") is None else c["cost"], "yes" if c.get("imported") else ""])
        return buf.getvalue()

    def _changed(self) -> None:
        self._save(now=True)
        self._notify_entities()
        self._schedule_statistics()

    # ------------------------------------------------------------ long-term statistics (monthly chart)

    def statistic_ids(self) -> dict[str, str]:
        suffix = "" if self.is_first_entry else f"_{self.short}"
        return {k: f"{DOMAIN}:{k}{suffix}" for k in ("energy_ac", "energy_dc", "cost")}

    @property
    def is_first_entry(self) -> bool:
        entries = sorted(self.hass.config_entries.async_entries(DOMAIN), key=lambda e: e.entry_id)
        return not entries or entries[0].entry_id == self.entry.entry_id

    def _schedule_statistics(self) -> None:
        if self._stats_timer:
            self._stats_timer()
        self._stats_timer = async_call_later(self.hass, 10, self._rebuild_statistics)

    async def _rebuild_statistics(self, _now=None) -> None:
        """Rewrites the monthly chart's series from the diary, imported charges included (one point per charge
        hour). Cleared first, so deleted or edited charges do not linger."""
        self._stats_timer = None
        if "recorder" not in self.hass.config.components:
            return
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.models import StatisticMeanType
        from homeassistant.components.recorder.statistics import async_add_external_statistics

        ids = self.statistic_ids()
        tz = dt_util.get_default_time_zone()
        series: dict[str, dict[datetime, float]] = {k: {} for k in ids}
        for c in self.charges:
            hour = datetime.fromtimestamp(c["start"], tz).replace(minute=0, second=0, microsecond=0)
            kind = "energy_dc" if c.get("kind") == "DC" else "energy_ac"
            series[kind][hour] = series[kind].get(hour, 0.0) + float(c.get("kwh") or 0)
            if c.get("cost"):
                series["cost"][hour] = series["cost"].get(hour, 0.0) + float(c["cost"])
        # Queued in the recorder before the imports below, so they run in this order.
        get_instance(self.hass).async_clear_statistics(list(ids.values()))
        units = {"energy_ac": ("kWh", "energy"), "energy_dc": ("kWh", "energy"), "cost": (self.currency, None)}
        names = {"energy_ac": "EX5 kWh AC", "energy_dc": "EX5 kWh DC", "cost": "EX5 cost"}
        for key, points in series.items():
            if not points:
                continue
            total, stats = 0.0, []
            for hour in sorted(points):
                total += points[hour]
                stats.append({"start": hour, "state": round(total, 3), "sum": round(total, 3)})
            unit, unit_class = units[key]
            async_add_external_statistics(self.hass, {
                "has_sum": True, "mean_type": StatisticMeanType.NONE, "name": names[key], "source": DOMAIN,
                "statistic_id": ids[key], "unit_class": unit_class, "unit_of_measurement": unit,
            }, stats)

    # ------------------------------------------------------------ notifications

    def _duration(self, minutes: int) -> str:
        return self.t("hours", h=minutes // 60, m=minutes % 60) if minutes >= 60 else self.t("minutes", m=minutes)

    async def _send(self, title: str, message: str, actions: list | None = None) -> None:
        service = self.options.get(CONF_NOTIFY)
        if not service:
            return
        domain, _, name = service.partition(".")
        data: dict[str, Any] = {"title": title, "message": message, "data": {"tag": f"{DOMAIN}_{self.short}"}}
        if actions:
            data["data"]["actions"] = actions
        try:
            await self.hass.services.async_call(domain, name, data, blocking=False)
        except Exception as err:  # noqa: BLE001 - a missing phone must not break charge recording
            _LOGGER.warning("Could not send notification via %s: %s", service, err)

    def _text_action(self, action: str, title: str, example: str) -> dict:
        return {"action": action, "title": title, "behavior": "textInput",
                "textInputButtonTitle": self.t("save"), "textInputPlaceholder": example}

    async def _notify_finished(self, c: dict) -> None:
        msg = self.t("finished", place=c["place"], kwh=core.fmt_number(c["kwh"], 1, self.language),
                     duration=self._duration(c["minutes"]), b0=int(round(c["battery_start"])),
                     b1=int(round(c["battery_end"])))
        actions = None
        if c["cost"] is None:
            msg += " " + self.t("finished_ask")
            actions = [
                self._text_action(ACTION_COST.format(self.short), self.t("inform_cost"),
                                  core.fmt_number(45.9, 2, self.language)),
                self._text_action(ACTION_KWH.format(self.short), self.t("inform_kwh"),
                                  core.fmt_number(43.98, 2, self.language)),
            ]
        elif c["cost"] == 0:
            msg += " " + self.t("finished_free")
        else:
            msg += " " + self.t("finished_fixed", cost=self.money(c["cost"]),
                                price=self.money(c["cost"] / c["kwh"]) if c["kwh"] else "-")
        await self._send(self.t("finished_title", kind=c["kind"]), msg, actions)

    @callback
    def _on_notification(self, event: Event) -> None:
        action = event.data.get("action")
        if action not in (ACTION_COST.format(self.short), ACTION_KWH.format(self.short)):
            return
        value = core.parse_number(event.data.get("reply_text"))
        if value is None or value < 0:
            return
        if action == ACTION_COST.format(self.short):
            c = self.set_cost(value)
            if c is None:
                self.hass.async_create_task(self._send(self.t("cost_title"), self.t("nothing_pending")))
                return
            price = self.money(c["cost"] / c["kwh"]) if c.get("kwh") else "-"
            msg = self.t("cost_saved", cost=self.money(c["cost"]), price=price,
                         month_cost=self.money(self.summary(self.current_month)["cost"]))
            actions = None
            if c.get("rule") == core.RULE_ASK and c.get("kwh_station") is None:
                actions = [self._text_action(ACTION_KWH.format(self.short), self.t("inform_kwh"),
                                             core.fmt_number(43.98, 2, self.language))]
            self.hass.async_create_task(self._send(self.t("cost_title"), msg, actions))
        else:
            if not 0.5 <= value <= 200:
                return
            before = self.pending_station_kwh()
            measured = float(before.get("kwh") or 0) if before else 0.0
            c = self.set_station_kwh(value)
            if c is None:
                self.hass.async_create_task(self._send(self.t("kwh_title"), self.t("nothing_pending")))
                return
            msg = self.t("kwh_saved", kwh=core.fmt_number(value, 2, self.language),
                         measured=core.fmt_number(measured, 1, self.language))
            actions = None
            if c.get("cost") is None:
                actions = [self._text_action(ACTION_COST.format(self.short), self.t("inform_cost"),
                                             core.fmt_number(45.9, 2, self.language))]
            self.hass.async_create_task(self._send(self.t("kwh_title"), msg, actions))

    # ------------------------------------------------------------ for the entities

    def last_charge_text(self) -> str | None:
        c = self.last_charge()
        if c is None:
            return None
        tz = dt_util.get_default_time_zone()
        when = datetime.fromtimestamp(c["start"], tz).strftime("%d/%m %H:%M" if self.lang == "pt" else "%m/%d %H:%M")
        if c.get("cost") is None:
            cost = self.t("summary_pending")
        elif c["cost"] == 0:
            cost = self.t("summary_free")
        else:
            cost = self.money(c["cost"])
        parts = [when, c.get("kind", ""), c.get("place", ""), f"{core.fmt_number(c['kwh'], 1, self.language)} kWh",
                 f"{int(round(c.get('battery_start', 0)))}→{int(round(c.get('battery_end', 0)))}%",
                 self._duration(int(c.get("minutes") or 0)), cost]
        return " · ".join(p for p in parts if p)[:255]

    @property
    def range_entity(self) -> str | None:
        return self.entities.get(KEY_RANGE)
