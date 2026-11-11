"""Unit tests for the pure logic (run with: python3 -m unittest discover tests)."""
import importlib.util
import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone

_CORE = pathlib.Path(__file__).parents[1] / "custom_components" / "ex5_insights" / "core.py"
_spec = importlib.util.spec_from_file_location("core", _CORE)
core = importlib.util.module_from_spec(_spec)
sys.modules["core"] = core  # dataclasses look the module up while it loads
_spec.loader.exec_module(core)

BRT = timezone(timedelta(hours=-3))
CAP = 60.22


def ts(s):
    return datetime.fromisoformat(s).replace(tzinfo=BRT).timestamp()


class Places(unittest.TestCase):
    def test_nearest_inside_radius(self):
        a = core.Place("A", -15.80, -47.90, 300)
        b = core.Place("B", -15.8005, -47.9005, 300)
        self.assertEqual(core.find_place([a, b], -15.8006, -47.9006).name, "B")
        self.assertIsNone(core.find_place([a], -15.9, -47.9))
        self.assertIsNone(core.find_place([a], None, None))

    def test_cost_rules(self):
        self.assertEqual(core.charge_cost(17.71, core.RULE_FIXED, 0.182347), 3.23)
        self.assertEqual(core.charge_cost(10, core.RULE_FREE, 5), 0.0)
        self.assertIsNone(core.charge_cost(10, core.RULE_ASK, 0))

    def test_place_dc_rule(self):
        p = core.Place.from_dict({"name": "X", "latitude": 0, "longitude": 0, "rule": "free"})
        self.assertEqual(p.rule_for("AC"), ("free", 0.0))
        self.assertEqual(p.rule_for("DC"), ("ask", 0.0))


class Session(unittest.TestCase):
    def test_integration_left_riemann(self):
        t0 = ts("2026-11-05T14:00:00")
        s = core.ChargeSession(start=t0, battery_start=30, power_time=t0)
        s.add_power(t0, 6.0, "AC", CAP)
        s.add_power(t0 + 1800, 6.0, "AC", CAP)  # 30 min at 6 kW = 3 kWh
        r = s.result(t0 + 3600, 40, CAP)  # another 30 min
        self.assertAlmostEqual(r["kwh"], 6.0, places=2)
        self.assertEqual(r["kind"], "AC")
        self.assertEqual(r["minutes"], 60)
        self.assertTrue(r["valid"])

    def test_dc_only_after_settle(self):
        t0 = ts("2026-11-02T20:39:00")
        s = core.ChargeSession(start=t0, battery_start=29, power_time=t0)
        s.add_power(t0, 40, "DC", CAP)  # first reading says DC: ignored (could be AC battery side)
        self.assertEqual(s.kind, "AC")
        s.add_power(t0 + 100, 40, "DC", CAP)
        self.assertEqual(s.kind, "DC")

    def test_ac_first_reading_dc_stays_ac(self):
        t0 = ts("2026-11-01T17:10:00")
        s = core.ChargeSession(start=t0, battery_start=73, power_time=t0)
        s.add_power(t0, 1.4, "DC", CAP)
        s.add_power(t0 + 13, 6.2, "AC", CAP)
        s.add_power(t0 + 600, 6.2, "AC", CAP)
        self.assertEqual(s.kind, "AC")

    def test_gap_both_sides_capped_by_battery(self):
        s = core.ChargeSession(start=0, battery_start=30)
        add = s.fill_gap(0, 3600, 6, 6, 30, 35, CAP)  # 6 kWh estimated, cap (5+1)% × 60.22 = 3.61
        self.assertAlmostEqual(add, 3.613, places=2)

    def test_gap_silent_start(self):
        s = core.ChargeSession(start=0, battery_start=29)
        add = s.fill_gap(0, 223, 0, 40, 29, 32, CAP)  # 3 points × 60.22% = 1.81 kWh, cap 40 kW × 223 s = 2.48
        self.assertAlmostEqual(add, 1.807, places=2)

    def test_short_silence_is_not_a_gap(self):
        s = core.ChargeSession(start=0, battery_start=29)
        self.assertEqual(s.fill_gap(0, 60, 6, 6, 29, 29, CAP), 0)

    def test_falls_back_to_battery(self):
        s = core.ChargeSession(start=0, battery_start=50, power_time=0)
        r = s.result(1800, 55, CAP)
        self.assertAlmostEqual(r["kwh"], 3.01, places=2)

    def test_roundtrip(self):
        s = core.ChargeSession(start=1, battery_start=2, kind="DC", energy=3.5)
        self.assertEqual(core.ChargeSession.from_dict(s.to_dict() | {"junk": 1}), s)


class Numbers(unittest.TestCase):
    def test_format(self):
        self.assertEqual(core.fmt_number(1595.49, 2, "pt-BR"), "1.595,49")
        self.assertEqual(core.fmt_number(1595.49, 2, "en"), "1,595.49")
        self.assertEqual(core.fmt_price(0.182347, "pt"), "0,182")
        self.assertEqual(core.fmt_price(1.3034, "en"), "1.30")

    def test_parse(self):
        self.assertEqual(core.parse_number("R$ 1.234,56"), 1234.56)
        self.assertEqual(core.parse_number("45,90"), 45.9)
        self.assertEqual(core.parse_number("38.5"), 38.5)
        self.assertEqual(core.parse_number("43,98 kWh"), 43.98)
        self.assertIsNone(core.parse_number("abc"))


class Months(unittest.TestCase):
    def test_summary(self):
        charges = [
            {"start": ts("2026-11-01T12:23:00"), "kind": "AC", "kwh": 28.58, "cost": 0.0},
            {"start": ts("2026-11-02T20:39:00"), "kind": "DC", "kwh": 43.98, "cost": 57.35},
            {"start": ts("2026-11-05T14:28:00"), "kind": "AC", "kwh": 17.71, "cost": 3.23},
            {"start": ts("2026-11-06T10:00:00"), "kind": "DC", "kwh": 20.0, "cost": None},
            {"start": ts("2026-10-29T18:07:00"), "kind": "DC", "kwh": 31.65, "cost": 43.70},
        ]
        s = core.month_summary(charges, "2026-11", 217.0, "pt-BR", BRT)
        self.assertEqual(s["charges"], 4)
        self.assertEqual((s["charges_ac"], s["charges_dc"]), (2, 2))
        self.assertEqual(s["cost"], 60.58)
        self.assertEqual(s["pending"], 1)
        self.assertEqual(s["rows"][0]["day"], "01/11")
        self.assertTrue(s["rows"][0]["free"])
        self.assertEqual(s["rows"][1]["price"], "1,30")
        self.assertEqual(s["rows"][2]["price"], "0,182")
        self.assertTrue(s["rows"][3]["pending"])
        self.assertEqual(s["consumption"], round(110.27 / 217 * 100, 1))

    def test_distance(self):
        marks = {"2026-10": 24100.0, "2026-11": 24115.0}
        self.assertEqual(core.month_distance("2026-10", marks, 24332, {}), 15.0)
        self.assertEqual(core.month_distance("2026-11", marks, 24332, {}), 217.0)
        self.assertEqual(core.month_distance("2026-01", marks, 24332, {"2026-01": 4000}), 4000.0)
        self.assertIsNone(core.month_distance("2026-02", marks, 24332, {}))

    def test_months_between(self):
        self.assertEqual(core.months_between("2025-11", "2026-02"), ["2026-02", "2026-01", "2025-12", "2025-11"])


SHEET = """,Data,Sequência,Custo kWh,Valor Total,Tempo (min),Carga kWh,Potência kW,Rede/App,Local,Cidade,PlugShare,Odômetro,kWh/100km
IDA,15/01/2026,1,"R$ 2,40","R$ 24,85",15,"9,52",40,Rede A,Hotel A,Cidade A - GO,"x | y",,
,15/01/2026,4,"R$ 1,29","R$ 55,18",668,"42,77",22,Rede B,Hotel B,Cidade B - MG,z,,
,18/01/2026,11,"R$ 1,85","R$ 51,32",37,"27,74",50,Rede C,Restaurante C,Cidade C - PR,w,"2189,2","16,3"
,,,,,,,,,,,,,
,,,"R$ 2,05","R$ 1.595,49",42,"775,897",,,,,,,
,,,média (R$),total (R$),média (min),total (kWh),,,,,,,
"""


class Import(unittest.TestCase):
    def test_brazilian_spreadsheet(self):
        rows, problems = core.parse_charges_csv(SHEET, BRT)
        self.assertEqual(problems, [])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["kind"], "DC")
        self.assertEqual(rows[1]["kind"], "AC")  # 22 kW
        self.assertEqual(rows[0]["cost"], 24.85)
        self.assertEqual(rows[0]["kwh"], 9.52)
        self.assertEqual(rows[0]["minutes"], 15)
        self.assertEqual(rows[2]["odometer"], 2189.2)
        self.assertTrue(rows[0]["date_only"])
        self.assertEqual(rows[0]["place"], "Hotel A")
        self.assertEqual(core.month_key(rows[0]["start"], BRT), "2026-01")

    def test_english_with_time(self):
        text = "date,time,type,kwh,cost\n2026-03-01,08:15,DC,30.5,61.00\n2026-03-02,,AC,10,\n"
        rows, _ = core.parse_charges_csv(text, BRT)
        self.assertFalse(rows[0]["date_only"])
        self.assertEqual(datetime.fromtimestamp(rows[0]["start"], BRT).strftime("%H:%M"), "08:15")
        self.assertIsNone(rows[1]["cost"])

    def test_missing_columns(self):
        rows, problems = core.parse_charges_csv("a,b\n1,2\n", BRT)
        self.assertEqual(rows, [])
        self.assertTrue(problems)


if __name__ == "__main__":
    unittest.main()
