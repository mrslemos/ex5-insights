"""Pure logic for EX5 Insights (no Home Assistant imports, so it can be unit tested on its own).

Pieces:
- ChargeSession: one charge in progress (energy integration, gap filling, AC/DC detection).
- Place / cost rules: where the car charged and how much it cost.
- Diary helpers: month summaries, the month table, CSV import.
- Number formatting for pt-BR and en.
"""
from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime

# A charge is "flowing" above this power (kW); the car reports small values when idle.
POWER_ON_KW = 0.3
# Readings closer than this (s) are normal; a longer silence while charging is a gap to fill.
GAP_SECONDS = 90
# The first readings of an AC charge sometimes come from the battery side and say "DC" (seen 01/11/2026):
# ignore the supply type for this long after power first appears.
TYPE_SETTLE_SECONDS = 90
# A charge counts only with at least this much energy or 1 battery point.
MIN_KWH = 0.2

RULE_FREE = "free"
RULE_FIXED = "fixed"
RULE_ASK = "ask"
RULES = (RULE_FREE, RULE_FIXED, RULE_ASK)


# ---------------------------------------------------------------- places and cost


@dataclass
class Place:
    """A charging place defined by the user."""

    name: str
    latitude: float
    longitude: float
    radius: float = 300.0  # meters
    rule: str = RULE_ASK  # for AC charges; DC always asks unless dc_rule says otherwise
    tariff: float = 0.0  # per kWh, for RULE_FIXED
    dc_rule: str = RULE_ASK
    dc_tariff: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "Place":
        return cls(
            name=str(d.get("name", "")),
            latitude=float(d.get("latitude", 0)),
            longitude=float(d.get("longitude", 0)),
            radius=float(d.get("radius", 300)),
            rule=d.get("rule", RULE_ASK) if d.get("rule") in RULES else RULE_ASK,
            tariff=float(d.get("tariff", 0) or 0),
            dc_rule=d.get("dc_rule", RULE_ASK) if d.get("dc_rule") in RULES else RULE_ASK,
            dc_tariff=float(d.get("dc_tariff", 0) or 0),
        )

    def rule_for(self, kind: str) -> tuple[str, float]:
        return (self.dc_rule, self.dc_tariff) if kind == "DC" else (self.rule, self.tariff)


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def find_place(places: list[Place], lat: float | None, lon: float | None) -> Place | None:
    """The nearest place whose radius contains the point."""
    if lat is None or lon is None:
        return None
    best, best_d = None, None
    for p in places:
        d = distance_m(lat, lon, p.latitude, p.longitude)
        if d <= p.radius and (best_d is None or d < best_d):
            best, best_d = p, d
    return best


def charge_cost(kwh: float, rule: str, tariff: float) -> float | None:
    """Cost of a charge: 0 if free, kWh × tariff if fixed, None if it must be asked."""
    if rule == RULE_FREE:
        return 0.0
    if rule == RULE_FIXED:
        return round(kwh * tariff, 2)
    return None


# ---------------------------------------------------------------- charge session


@dataclass
class ChargeSession:
    """A charge in progress. Times are POSIX timestamps (s), energy in kWh, battery in %."""

    start: float
    battery_start: float
    odometer: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    kind: str = "AC"
    energy: float = 0.0  # integrated from the charging power
    gaps: float = 0.0  # filled in where there were no readings
    power: float = 0.0  # last power reading (kW)
    power_time: float = 0.0  # when it was read (s)
    power_on_since: float | None = None  # first time power went above POWER_ON_KW
    battery: float | None = None  # last battery reading
    battery_time: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ChargeSession":
        names = {f for f in cls.__dataclass_fields__}  # noqa: SLF001
        return cls(**{k: v for k, v in d.items() if k in names})

    # The car's power is a step function between readings: integrate the last value (left Riemann sum).
    def advance(self, now: float) -> None:
        if self.power_time and now > self.power_time:
            self.energy += max(self.power, 0.0) * (now - self.power_time) / 3600.0
        self.power_time = max(now, self.power_time)

    def add_power(self, now: float, power: float, supply: str | None, capacity: float) -> None:
        """New power reading. Fills the gap if HA was not running since the last one (see fill_gap)."""
        self.advance(now)
        self.power = max(power, 0.0)
        if self.power > POWER_ON_KW:
            if self.power_on_since is None:
                self.power_on_since = now
            if supply == "DC" and now - self.power_on_since >= TYPE_SETTLE_SECONDS:
                self.kind = "DC"

    def add_battery(self, now: float, battery: float) -> None:
        self.battery, self.battery_time = battery, now

    def fill_gap(self, since: float, now: float, power_before: float, power_now: float,
                 battery_before: float | None, battery_now: float | None, capacity: float) -> float:
        """Energy for a stretch without readings (HA restarting, car silent). Returns what was added.

        Charging before and after: average power × time. Starting in silence: battery rise × capacity.
        Ending in silence: the smaller of power before × time and battery rise × capacity.
        Always capped by the battery rise (+1 point, because the car reports whole percent).
        """
        dt = now - since
        if dt <= GAP_SECONDS or dt > 12 * 3600:
            return 0.0
        rise = None
        if battery_before is not None and battery_now is not None:
            rise = max(battery_now - battery_before, 0.0)
        if power_before > POWER_ON_KW and power_now > POWER_ON_KW:
            est = (power_before + power_now) / 2 * dt / 3600
            cap = (rise + 1) * capacity / 100 if rise is not None else est
        elif power_now > POWER_ON_KW:
            est = rise * capacity / 100 if rise is not None else 0.0
            cap = power_now * dt / 3600
        elif power_before > POWER_ON_KW:
            est = power_before * dt / 3600
            cap = rise * capacity / 100 if rise is not None else est
        else:
            return 0.0
        add = max(min(est, cap), 0.0)
        self.gaps += add
        return add

    def result(self, end: float, battery_end: float | None, capacity: float) -> dict:
        """Final numbers for the diary."""
        self.advance(end)
        b_end = battery_end if battery_end is not None else self.battery_start
        kwh_battery = max(b_end - self.battery_start, 0.0) * capacity / 100
        measured = self.energy + self.gaps
        kwh = measured if measured >= 0.1 else kwh_battery
        return {
            "start": self.start,
            "end": end,
            "kind": self.kind,
            "battery_start": round(self.battery_start, 1),
            "battery_end": round(b_end, 1),
            "kwh": round(kwh, 2),
            "kwh_measured": round(self.energy, 2),
            "kwh_gaps": round(self.gaps, 2),
            "kwh_battery": round(kwh_battery, 2),
            "minutes": int(round((end - self.start) / 60)),
            "odometer": self.odometer,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "valid": kwh >= MIN_KWH or (b_end - self.battery_start) >= 1,
        }


# ---------------------------------------------------------------- formatting


def fmt_number(x: float, decimals: int = 2, lang: str = "en") -> str:
    """1,234.56 in English, 1.234,56 in Portuguese."""
    s = f"{x:,.{decimals}f}"
    if lang.lower().startswith("pt"):
        s = s.replace(",", "_").replace(".", ",").replace("_", ".")
    return s


def fmt_price(x: float, lang: str) -> str:
    """Price per kWh: 3 decimals below 1 (0.182), 2 above (1.30)."""
    return fmt_number(x, 2 if x >= 1 else 3, lang)


def parse_number(text) -> float | None:
    """Reads '45,90', 'R$ 1.234,56', '38.5', '43,98 kWh'. None if not a number."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    t = re.sub(r"[^0-9,.\-]", "", str(text))
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


# ---------------------------------------------------------------- diary and months


def month_key(ts: float, tz=None) -> str:
    return datetime.fromtimestamp(ts, tz).strftime("%Y-%m")


def month_summary(charges: list[dict], month: str, distance_km: float | None, lang: str, tz=None) -> dict:
    """Totals and the table rows for one month ("YYYY-MM").

    Each charge: start (timestamp), kind, kwh, cost (None = not informed yet), date_only (True if imported without
    a time). Cost None stays out of the totals and is counted as pending.
    """
    rows, kwh = [], {"AC": 0.0, "DC": 0.0}
    count = {"AC": 0, "DC": 0}
    cost_total, pending = 0.0, 0
    for c in sorted(charges, key=lambda c: (c["start"], c.get("seq", 0))):
        if month_key(c["start"], tz) != month:
            continue
        kind = "DC" if c.get("kind") == "DC" else "AC"
        k = float(c.get("kwh") or 0)
        kwh[kind] += k
        count[kind] += 1
        cost = c.get("cost")
        if cost is None:
            pending += 1
            price, total = None, None
        else:
            cost_total += float(cost)
            price = float(cost) / k if k > 0 and float(cost) > 0 else (0.0 if float(cost) == 0 else None)
            total = float(cost)
        d = datetime.fromtimestamp(c["start"], tz)
        rows.append({
            "id": c.get("id"),
            "day": d.strftime("%d/%m") if lang.lower().startswith("pt") else d.strftime("%m/%d"),
            "time": "" if c.get("date_only") else d.strftime("%H:%M"),
            "kind": kind,
            "place": c.get("place", ""),
            "kwh": fmt_number(k, 1, lang),
            "price": None if price is None else ("" if price == 0 else fmt_price(price, lang)),
            "total": None if total is None else fmt_number(total, 2, lang),
            "free": cost is not None and float(cost) == 0,
            "pending": cost is None,
        })
    kwh_all = kwh["AC"] + kwh["DC"]
    out = {
        "month": month,
        "charges": count["AC"] + count["DC"],
        "charges_ac": count["AC"],
        "charges_dc": count["DC"],
        "kwh": round(kwh_all, 2),
        "kwh_ac": round(kwh["AC"], 2),
        "kwh_dc": round(kwh["DC"], 2),
        "cost": round(cost_total, 2),
        "pending": pending,
        "distance": None if distance_km is None else round(distance_km, 1),
        "consumption": None,
        "cost_per_km": None,
        "rows": rows,
        "total_row": {
            "kwh": fmt_number(kwh_all, 1, lang),
            "price": fmt_price(cost_total / kwh_all, lang) if kwh_all > 0 and cost_total > 0 else "",
            "total": fmt_number(cost_total, 2, lang),
        },
    }
    # Consumption and cost per km only from 20 km, otherwise the numbers are noise.
    if distance_km is not None and distance_km >= 20:
        out["consumption"] = round(kwh_all / distance_km * 100, 1)
        out["cost_per_km"] = round(cost_total / distance_km, 2)
    return out


def month_distance(month: str, odometer_marks: dict[str, float], current_odometer: float | None,
                   overrides: dict[str, float]) -> float | None:
    """km driven in a month: the user's override, else odometer at the next month's first reading (or now) minus
    the odometer at this month's first reading."""
    if month in overrides:
        return float(overrides[month])
    start = odometer_marks.get(month)
    if start is None:
        return None
    later = sorted(m for m in odometer_marks if m > month)
    end = odometer_marks[later[0]] if later else current_odometer
    if end is None:
        return None
    return max(end - start, 0.0)


def months_between(first: str, last: str) -> list[str]:
    """['2026-01', ..., '2026-11'] (inclusive), newest first."""
    y, m = map(int, first.split("-"))
    ly, lm = map(int, last.split("-"))
    out = []
    while (y, m) <= (ly, lm):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return list(reversed(out))


# ---------------------------------------------------------------- CSV import

# Accepted headers (English or Portuguese). Only start/date and kwh are required.
_HEADERS = {
    "start": ("start", "inicio", "início", "data", "date"),
    "time": ("time", "hora"),
    "kind": ("type", "kind", "tipo"),
    "place": ("place", "local"),
    "kwh": ("kwh", "carga kwh", "energia", "energy"),
    "cost": ("cost", "custo", "custo_rs", "valor total", "valor", "total"),
    "minutes": ("minutes", "minutos", "tempo (min)", "duration"),
    "odometer": ("odometer", "odometro", "odômetro", "odometro_km"),
    "power": ("power", "potência kw", "potencia kw", "potência", "potencia"),
}


def _parse_when(date_text: str, time_text: str, tz) -> tuple[float, bool] | None:
    date_text, time_text = (date_text or "").strip(), (time_text or "").strip()
    if not date_text:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{1,2}):(\d{2}))?", date_text)
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        hh, mm = (int(m[4]), int(m[5])) if m[4] else (None, None)
    else:
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?", date_text)
        if not m:
            return None
        d, mo, y = int(m[1]), int(m[2]), int(m[3])
        hh, mm = (int(m[4]), int(m[5])) if m[4] else (None, None)
    if hh is None and time_text:
        t = re.match(r"^(\d{1,2}):(\d{2})", time_text)
        if t:
            hh, mm = int(t[1]), int(t[2])
    date_only = hh is None
    dt = datetime(y, mo, d, hh if hh is not None else 12, mm or 0, tzinfo=tz)
    return dt.timestamp(), date_only


def parse_charges_csv(text: str, tz) -> tuple[list[dict], list[str]]:
    """Charges from a spreadsheet exported as CSV. Returns (charges, problems).

    Type: the column if present; else AC up to 22 kW of power, DC above; else AC. Cost missing = not informed.
    Rows without a date or kWh are skipped (totals, blank lines)."""
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = list(reader)
    if not rows:
        return [], ["empty file"]
    header = [h.strip().lower() for h in rows[0]]
    col = {}
    for key, names in _HEADERS.items():
        for i, h in enumerate(header):
            if h in names:
                col[key] = i
                break
    problems = []
    if "start" not in col or "kwh" not in col:
        return [], ["the file needs a date and a kWh column"]
    out = []
    for n, r in enumerate(rows[1:], start=2):
        get = lambda k: r[col[k]].strip() if k in col and col[k] < len(r) else ""  # noqa: E731
        when = _parse_when(get("start"), get("time"), tz)
        kwh = parse_number(get("kwh"))
        if when is None or kwh is None or kwh <= 0:
            if any(x.strip() for x in r) and when is None and get("start"):
                problems.append(f"line {n}: date not understood")
            continue
        kind = get("kind").upper()
        if kind not in ("AC", "DC"):
            power = parse_number(get("power"))
            kind = "DC" if power is not None and power > 22 else "AC"
        cost = parse_number(get("cost"))
        minutes = parse_number(get("minutes"))
        odo = parse_number(get("odometer"))
        out.append({
            "start": when[0],
            "date_only": when[1],
            "kind": kind,
            "place": get("place"),
            "kwh": round(kwh, 3),
            "kwh_station": round(kwh, 3),
            "cost": None if cost is None else round(cost, 2),
            "minutes": None if minutes is None else int(minutes),
            "odometer": odo,
            "imported": True,
            "seq": n,
        })
    return out, problems
