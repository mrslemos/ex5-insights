"""Where a point is, offline: the Brazilian municipality and, in the Federal District, the administrative region.

Data in the geo folder (see geo/SOURCES.md). The small index (names, seats, boxes, offsets) is read once; a
municipality's boundary is read from disk only when the point falls inside its box. No Home Assistant imports, so it
can be unit tested on its own. Call it from an executor: it reads files.
"""
from __future__ import annotations

import csv
import math
import os

GEO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geo")
MUNICIPALITIES = os.path.join(GEO, "municipios_br.csv")
BOUNDARIES = os.path.join(GEO, "municipios_contornos.txt")
DF_REGIONS = os.path.join(GEO, "ras_df.txt")

# Outside every municipality box and farther than this from the nearest seat: not in Brazil, no name.
MAX_SEAT_KM = 60.0


def _inside(lat: float, lon: float, rings: list[list[tuple[float, float]]]) -> bool:
    """Even-odd rule over all rings (holes respected). Rings are lists of (lon, lat)."""
    inside = False
    for ring in rings:
        n = len(ring)
        for k in range(n):
            x1, y1 = ring[k]
            x2, y2 = ring[(k + 1) % n]
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                inside = not inside
    return inside


def _rings(text: str) -> list[list[tuple[float, float]]]:
    return [[tuple(map(float, pair.split())) for pair in ring.split(",")] for ring in text.split("|")]


class Places:
    """Municipality and DF region lookup. Thread safe for reading after the first call."""

    def __init__(self) -> None:
        self._index: list[tuple] | None = None
        self._regions: list[tuple] | None = None

    def _load(self) -> None:
        if self._index is not None:
            return
        index = []
        with open(MUNICIPALITIES, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                index.append((float(r["lat_min"]), float(r["lat_max"]), float(r["lon_min"]), float(r["lon_max"]),
                              float(r["latitude"]), float(r["longitude"]), int(r["posicao"]), r["nome"], r["uf"]))
        regions = []
        if os.path.exists(DF_REGIONS):
            with open(DF_REGIONS, encoding="utf-8") as f:
                for line in f:
                    name, box, rings = line.rstrip("\n").split(";", 2)
                    x0, y0, x1, y1 = map(float, box.split())
                    regions.append((x0, y0, x1, y1, name, rings))
        self._index, self._regions = index, regions

    def municipality(self, lat: float, lon: float) -> tuple[str, str] | None:
        """(name, state) of the municipality containing the point. On a gap of the simplified boundaries (near a
        border), the one with the nearest seat. None outside Brazil."""
        self._load()
        candidates, best, nearest = [], None, None
        coslat = math.cos(math.radians(lat))
        for la0, la1, lo0, lo1, sla, slo, pos, name, uf in self._index:
            if la0 <= lat <= la1 and lo0 <= lon <= lo1:
                candidates.append((pos, name, uf))
            d = (sla - lat) ** 2 + ((slo - lon) * coslat) ** 2
            if best is None or d < best:
                best, nearest = d, (name, uf)
        if candidates:
            with open(BOUNDARIES, "rb") as f:
                for pos, name, uf in candidates:
                    f.seek(pos)
                    line = f.readline().decode("utf-8").strip()
                    if _inside(lat, lon, _rings(line.split(";", 1)[1])):
                        return name, uf
            return nearest
        if best is not None and math.sqrt(best) * 111.2 <= MAX_SEAT_KM:
            return nearest
        return None

    def df_region(self, lat: float, lon: float) -> str:
        """Administrative region of the Federal District containing the point ("" if none)."""
        self._load()
        for x0, y0, x1, y1, name, rings in self._regions:
            if x0 <= lon <= x1 and y0 <= lat <= y1 and _inside(lat, lon, _rings(rings)):
                return name
        return ""

    def name(self, lat: float | None, lon: float | None) -> str:
        """Short name for the diary: the DF region in Brasília, else the municipality, else ""."""
        if lat is None or lon is None:
            return ""
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return ""
        if lat == 0 and lon == 0:
            return ""
        found = self.municipality(lat, lon)
        if found is None:
            return ""
        name, uf = found
        if name == "Brasília" and uf == "DF":
            return self.df_region(lat, lon) or name
        return name


PLACES = Places()
