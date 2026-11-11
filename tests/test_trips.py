"""Unit tests for trips, real range, battery capacity and the offline place names."""
import importlib.util
import pathlib
import unittest
from datetime import datetime, timedelta, timezone

_DIR = pathlib.Path(__file__).parents[1] / "custom_components" / "ex5_insights"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


trips = _load("trips")
geo = _load("geo")
BRT = timezone(timedelta(hours=-3))


def ts(s):
    return datetime.fromisoformat(s).replace(tzinfo=BRT).timestamp()


def straight_path(start, km, minutes, every=60, lat=-15.8, lon=-47.9):
    """Points along a parallel, evenly spaced in time, plus the parked starting point."""
    n = max(int(minutes * 60 / every), 1)
    dlon = km / (111.32 * 0.9622) / n  # cos(15.8°) ≈ 0.9622
    pts = [[lat, lon, start - 90]]  # where the car was parked, timed late
    for i in range(n + 1):
        pts.append([lat, round(lon + i * dlon, 5), start + i * every])
    return pts


class Highway(unittest.TestCase):
    def test_fast_path_is_highway(self):
        pts = straight_path(ts("2026-11-01T08:00"), 40, 30)  # 80 km/h
        self.assertGreater(trips.fast_fraction(pts), 0.9)
        self.assertTrue(trips.is_highway(40, 30, trips.fast_fraction(pts)))

    def test_slow_path_is_city(self):
        pts = straight_path(ts("2026-11-01T08:00"), 15, 30)  # 30 km/h
        self.assertLess(trips.fast_fraction(pts), 0.1)
        self.assertFalse(trips.is_highway(15, 30, trips.fast_fraction(pts)))

    def test_short_trip_never_highway(self):
        self.assertFalse(trips.is_highway(9.9, 5, 1.0))

    def test_without_path_old_rule(self):
        self.assertTrue(trips.is_highway(31, 60, None))
        self.assertTrue(trips.is_highway(20, 15, None))  # 80 km/h average
        self.assertFalse(trips.is_highway(20, 40, None))


class PathView(unittest.TestCase):
    def test_speeds_and_totals(self):
        start = ts("2026-11-01T08:00")
        v = trips.path_view(straight_path(start, 40, 30), BRT)
        self.assertEqual(len(v["points"]), 32)
        self.assertIsNone(v["points"][0][3])  # the parked point has no speed
        self.assertAlmostEqual(v["avg_speed"], 80, delta=2)
        self.assertAlmostEqual(v["km"], 40, delta=0.5)
        self.assertEqual(v["points"][1][2], "08:00")
        # every point but the first gets a color speed (its own or a neighbor's)
        self.assertTrue(all(p[4] is not None for p in v["points"][1:]))

    def test_gps_jump_has_no_speed(self):
        start = ts("2026-11-01T08:00")
        pts = [[-15.8, -47.9, start - 60], [-15.8, -47.9, start], [-15.8, -47.9, start + 100],
               [-16.8, -47.9, start + 200]]  # 111 km in 100 s
        v = trips.path_view(pts, BRT)
        self.assertIsNone(v["points"][3][3])

    def test_maps_link_at_most_ten_points(self):
        link = trips.maps_link(straight_path(ts("2026-11-01T08:00"), 40, 30))
        self.assertTrue(link.startswith("https://www.google.com/maps/dir/"))
        self.assertEqual(link.count("/-15.8,"), 10)
        self.assertEqual(trips.maps_link([[-15.8, -47.9, 0]]), "")


class RealRange(unittest.TestCase):
    def test_full_charge_and_parked_use(self):
        t0 = ts("2026-11-01T08:00")
        ts_ = [
            {"start": t0, "end": t0 + 3600, "battery_start": 100, "battery_end": 60, "km": 160, "highway": True},
            {"start": t0 + 7200, "end": t0 + 9000, "battery_start": 58, "battery_end": 48, "km": 30, "highway": False},
        ]
        charges = [{"start": t0 + 20000, "end": t0 + 30000, "battery_start": 46, "battery_end": 100}]
        r = trips.real_range(ts_, charges, 100, "parked", 60, t0 + 40000)
        # 40 + 2 (parked) + 10 + 2 (parked) = 54 % for 190 km
        self.assertEqual(r["all"]["km"], 190)
        self.assertEqual(r["all"]["battery_pct"], 54)
        self.assertEqual(r["all"]["km_per_charge"], round(190 / 54 * 100))
        self.assertTrue(r["all"]["preview"])
        self.assertEqual(r["all"]["parked_pct"], 4)
        self.assertEqual(r["all"]["range_now"], r["all"]["km_per_charge"])
        self.assertEqual(r["highway"]["trips"], 1)
        self.assertEqual(r["city"]["trips"], 1)

    def test_parked_now_counts_while_parked(self):
        t0 = ts("2026-11-01T08:00")
        ts_ = [{"start": t0, "end": t0 + 3600, "battery_start": 90, "battery_end": 50, "km": 150, "highway": True}]
        parked = trips.real_range(ts_, [], 45, "parked", 60, t0 + 9000)
        driving = trips.real_range(ts_, [], 45, "driving", 60, t0 + 9000)
        self.assertEqual(parked["all"]["battery_pct"], 45)
        self.assertEqual(driving["all"]["battery_pct"], 40)

    def test_nothing_yet(self):
        r = trips.real_range([], [], 80, "parked", 60, 0)
        self.assertIsNone(r["all"]["km_per_charge"])
        self.assertIsNone(r["all"]["range_now"])


class Capacity(unittest.TestCase):
    def test_measured_between_steps(self):
        m = trips.CapacityMeter(power_time=0)
        m.add_pack_power(0, -12.0)  # 12 kW into the pack: 0.2 kWh a minute
        battery, now = 30.0, 0.0
        while battery < 60:
            now += 60
            m.advance(now)
            # 0.6 kWh per point with 60 kWh: one point every 3 minutes
            if m.energy - (m.last_energy if m.last_pct else 0) >= 0.599:
                m.add_battery(now, battery, battery + 1)
                battery += 1
        r = m.result()
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r["capacity"], 60, delta=2)

    def test_small_or_interrupted_charge_ignored(self):
        m = trips.CapacityMeter(power_time=0)
        m.add_pack_power(0, -11)
        m.add_battery(60, 50, 51)
        m.add_battery(600, 60, 61)
        self.assertIsNone(m.result())  # 10 points only
        m.add_battery(3000, 80, 81)
        m.valid = False
        self.assertIsNone(m.result())

    def test_above_95_does_not_count(self):
        m = trips.CapacityMeter(power_time=0)
        m.add_battery(10, 95, 96)
        self.assertIsNone(m.last_pct)

    def test_average_of_last_three_and_factor(self):
        ms = [{"capacity": 50}, {"capacity": 57.4}, {"capacity": 58.1}, {"capacity": 57.75}]
        self.assertEqual(trips.measured_capacity(ms), 57.75)
        self.assertEqual(trips.measured_capacity(ms, 1.0156), round(57.75 * 1.0156, 2))
        self.assertIsNone(trips.measured_capacity([]))


class PlaceNames(unittest.TestCase):
    def test_brazil_and_federal_district(self):
        p = geo.Places()
        self.assertEqual(p.name(-15.7997, -47.8645), "Plano Piloto")  # National Congress
        self.assertEqual(p.name(-15.8410, -48.0270), "Águas Claras")
        self.assertEqual(p.name(-15.8176, -48.1428), "Ceilândia")  # Sol Nascente, shown as Ceilândia
        self.assertEqual(p.name(-16.6799, -49.2550), "Goiânia")
        self.assertEqual(p.name(-23.5503, -46.6340), "São Paulo")
        self.assertEqual(p.name(-25.6953, -54.4367), "Foz do Iguaçu")

    def test_outside_brazil_and_bad_input(self):
        p = geo.Places()
        self.assertEqual(p.name(-25.2637, -57.5759), "")  # Asunción
        self.assertEqual(p.name(38.72, -9.14), "")  # Lisbon
        self.assertEqual(p.name(None, None), "")
        self.assertEqual(p.name(0, 0), "")


if __name__ == "__main__":
    unittest.main()
