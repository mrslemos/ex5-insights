"""Pure logic for trips, real range and battery capacity (no Home Assistant imports, unit tested on its own).

A trip goes from one parking spot to the next. While the car moves, Geely Connect sends the position about once a
minute: that is the trip's path. Times are POSIX timestamps (s).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime

# A trip is the highway kind with at least this length and more than half of the distance at HIGHWAY_KMH or more.
HIGHWAY_MIN_KM = 10.0
HIGHWAY_KMH = 70.0
# GPS speed: positions arrive in bursts and with the time they reached Home Assistant, not the GPS time. Speeds use
# a window of at least this many seconds back (smaller windows gave false peaks of 170 km/h; the car's own speed
# sensor marked 135 at most). Above SPEED_MAX it is a GPS jump.
SPEED_WINDOW = 90
SPEED_MAX = 200
# Capacity: only charges that rose this many points, measured up to MAX_PCT (from 95 to 100 % the battery balances
# and the percentage moves slowly, which gave 64 kWh per 100 % instead of 58).
CAPACITY_MIN_POINTS = 20
CAPACITY_MAX_PCT = 95
CAPACITY_RANGE = (30.0, 70.0)
CAPACITY_AVERAGE_OF = 3
MAP_POINTS = 10


def km_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(min(h, 1.0)))


def clean_point(lat, lon) -> tuple[float, float] | None:
    """A valid coordinate rounded to 5 places (~1 m), or None."""
    try:
        la, lo = round(float(lat), 5), round(float(lon), 5)
    except (TypeError, ValueError):
        return None
    if (la == 0 and lo == 0) or not (-90 <= la <= 90 and -180 <= lo <= 180):
        return None
    return la, lo


# ---------------------------------------------------------------- one trip


def fast_fraction(points: list[list]) -> float | None:
    """Share of the distance driven at HIGHWAY_KMH or more, by GPS between points 20 s or more apart.

    points: [lat, lon, ts]. The first point is where the car was parked, timed when the trip was detected (late),
    so it is left out. None if there is no path long enough to measure."""
    pts = points[1:]
    total = fast = 0.0
    for a, b in zip(pts, pts[1:]):
        d = km_between(a, b)
        seg = b[2] - a[2]
        total += d
        if seg >= 20 and d / seg * 3600 >= HIGHWAY_KMH:
            fast += d
    return fast / total if total >= 1 else None


def is_highway(km: float, minutes: float, fraction: float | None) -> bool:
    """Highway trip: 10 km or more and over half of it fast, by the path. Without a path: more than 30 km or an
    average above 60 km/h. Short trips have few points that arrive in bursts and inflate the speed."""
    if km < HIGHWAY_MIN_KM:
        return False
    if fraction is not None:
        return fraction >= 0.5
    return km > 30 or (minutes > 0 and km / (minutes / 60) > 60)


def maps_link(points: list[list]) -> str:
    """Google Maps link through up to MAP_POINTS points spread along the path (Google redraws the route on the
    streets, so it is an approximation of the way taken)."""
    pts = [(p[0], p[1]) for p in points]
    if len(pts) < 2:
        return ""
    if len(pts) > MAP_POINTS:
        n = len(pts) - 1
        idx = sorted({round(i * n / (MAP_POINTS - 1)) for i in range(MAP_POINTS)})
        pts = [pts[i] for i in idx]
    return "https://www.google.com/maps/dir/" + "/".join(f"{la},{lo}" for la, lo in pts) + "/data=!4m2!4m1!3e0"


def path_view(points: list[list], tz=None) -> dict:
    """The path for the timeline card: each point [lat, lon, "HH:MM", km/h or None, km/h for the color or None],
    plus km, minutes, average and top speed (by GPS)."""
    raw = [(p[0], p[1], p[2]) for p in points if p and p[2] is not None]
    acc = [0.0] * len(raw)
    for i in range(2, len(raw)):
        acc[i] = acc[i - 1] + km_between(raw[i - 1], raw[i])
    out, km, vmax = [], 0.0, 0.0
    for i, (la, lo, t) in enumerate(raw):
        if i:
            km += km_between(raw[i - 1], (la, lo))
        vel = None
        if i >= 2:
            for k in range(i - 1, 0, -1):
                seg = t - raw[k][2]
                if seg >= SPEED_WINDOW:
                    v = (acc[i] - acc[k]) / seg * 3600
                    if v <= SPEED_MAX:
                        vel = round(v)
                        vmax = max(vmax, v)
                    break
        out.append([la, lo, datetime.fromtimestamp(t, tz).strftime("%H:%M"), vel, None])
    vels = [p[3] for p in out]
    for i in range(1, len(out)):
        if vels[i] is not None:
            out[i][4] = vels[i]
            continue
        for dist in range(1, len(out)):
            near = [j for j in (i - dist, i + dist) if 1 <= j < len(out) and vels[j] is not None]
            if near:
                out[i][4] = vels[near[0]]
                break
    minutes = (raw[-1][2] - raw[0][2]) / 60 if len(raw) > 1 else 0
    gps_minutes = (raw[-1][2] - raw[1][2]) / 60 if len(raw) > 2 else 0
    avg = round(acc[-1] / gps_minutes * 60) if raw and gps_minutes >= 1 and acc[-1] > 0 else None
    return {"points": out, "km": round(km, 1), "minutes": round(minutes), "avg_speed": avg,
            "max_speed": round(vmax) or None}


# ---------------------------------------------------------------- real range


def real_range(trips: list[dict], charges: list[dict], battery_now: float | None, state: str,
               capacity: float, now: float) -> dict:
    """km per 100 % of battery used (a real "full charge"), looking back until 100 % is summed.

    Used while driving = battery at departure - at arrival. Used while parked (climate, losses) = battery at the end
    of a trip or charge - at the start of the next one (and, parked now, down to the current battery). Highway and
    city use their own trips' battery plus the share of the parked use proportional to their km.
    state: "parked", "driving" or "charging". trips need start, end, battery_start, battery_end, km, highway;
    charges need start, end, battery_start, battery_end."""
    events = []
    for t in trips:
        if None in (t.get("start"), t.get("end"), t.get("battery_start"), t.get("battery_end"), t.get("km")):
            continue
        events.append((t["start"], t["end"], float(t["battery_start"]), float(t["battery_end"]),
                       (float(t["km"]), bool(t.get("highway")))))
    for c in charges:
        if None in (c.get("start"), c.get("end"), c.get("battery_start"), c.get("battery_end")):
            continue
        events.append((c["start"], c["end"], float(c["battery_start"]), float(c["battery_end"]), None))
    events.sort(key=lambda e: e[0])
    items = []  # (time, kind, pct, km, category)
    previous = None
    for start, end, b0, b1, trip in events:
        if previous is not None and previous - b0 > 0:
            items.append((start, "parked", previous - b0, 0.0, None))
        if trip:
            km, highway = trip
            items.append((end, "trip", max(b0 - b1, 0.0), km, "highway" if highway else "city"))
        previous = b1
    if state == "parked" and previous is not None and battery_now is not None and previous - battery_now > 0:
        items.append((now, "parked", previous - battery_now, 0.0, None))
    items.sort(key=lambda i: i[0], reverse=True)

    def summary(km, pct, n, parked):
        r = {"km_per_charge": round(km / pct * 100) if pct > 0 and km > 0 else None, "km": round(km, 1),
             "battery_pct": round(pct, 1), "trips": n, "preview": pct < 100, "kwh_100km": None, "range_now": None}
        if r["km_per_charge"]:
            r["kwh_100km"] = round(pct / 100 * capacity / km * 100, 1)
            if battery_now is not None:
                r["range_now"] = round(r["km_per_charge"] * battery_now / 100)
        if parked is not None:
            r["parked_pct"] = round(parked, 1)
        return r

    km = pct = parked = 0.0
    n = 0
    for _, kind, p, k, _c in items:
        if pct >= 100:
            break
        pct += p
        km += k
        if kind == "parked":
            parked += p
        else:
            n += 1
    out = {"all": summary(km, pct, n, parked)}
    extra_per_km = parked / km if km > 0 else 0.0
    for cat in ("highway", "city"):
        kc = pc = 0.0
        nc = 0
        for _, kind, p, k, c in items:
            if pc >= 100:
                break
            if kind == "trip" and c == cat:
                pc += p + extra_per_km * k
                kc += k
                nc += 1
        out[cat] = summary(kc, pc, nc, None)
    return out


# ---------------------------------------------------------------- battery capacity


@dataclass
class CapacityMeter:
    """Energy into the battery during one charge, between the first and the last time the percentage went up
    (the percentage is whole: measuring from one step to another avoids an error of up to 1 point at each end).
    Energy = pack power (negative while charging) summed over time."""

    energy: float = 0.0  # kWh into the pack since the charge began
    power: float = 0.0  # last pack power into the battery (kW, positive)
    power_time: float | None = None
    first_pct: float | None = None
    first_energy: float = 0.0
    last_pct: float | None = None
    last_energy: float = 0.0
    valid: bool = True  # False if Home Assistant restarted during the charge (the sum misses that stretch)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CapacityMeter":
        names = set(cls.__dataclass_fields__)  # noqa: SLF001
        return cls(**{k: v for k, v in d.items() if k in names})

    def advance(self, now: float) -> None:
        """Sum the last power up to now (called on each reading and every minute: the car does not repeat an
        unchanged value, so the last one holds until the next)."""
        if self.power_time is not None and now > self.power_time:
            self.energy += self.power * (now - self.power_time) / 3600
        self.power_time = now if self.power_time is None else max(now, self.power_time)

    def add_pack_power(self, now: float, pack_kw: float) -> None:
        self.advance(now)
        self.power = max(-pack_kw, 0.0)

    def add_battery(self, now: float, before: float | None, pct: float) -> None:
        """A battery reading during the charge; only rises up to CAPACITY_MAX_PCT count."""
        if before is None or pct <= before or pct > CAPACITY_MAX_PCT:
            return
        self.advance(now)
        if self.first_pct is None:
            self.first_pct, self.first_energy = pct, self.energy
        self.last_pct, self.last_energy = pct, self.energy

    def result(self) -> dict | None:
        """{"points", "kwh", "capacity"} if the charge counts, else None."""
        if not self.valid or self.first_pct is None or self.last_pct is None:
            return None
        points = self.last_pct - self.first_pct
        kwh = self.last_energy - self.first_energy
        if points < CAPACITY_MIN_POINTS or kwh <= 0:
            return None
        cap = kwh / points * 100
        if not CAPACITY_RANGE[0] < cap < CAPACITY_RANGE[1]:
            return None
        return {"points": round(points, 1), "kwh": round(kwh, 3), "capacity": round(cap, 2)}


def measured_capacity(measurements: list[dict], factor: float = 1.0) -> float | None:
    """Average of the latest measurements times the calibration factor (None if there are none)."""
    caps = [float(m["capacity"]) for m in measurements if m.get("capacity")]
    if not caps:
        return None
    last = caps[-CAPACITY_AVERAGE_OF:]
    return round(round(sum(last) / len(last), 2) * (factor or 1.0), 2)
