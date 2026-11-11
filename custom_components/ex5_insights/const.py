"""Constants for EX5 Insights."""
from __future__ import annotations

DOMAIN = "ex5_insights"
VERSION = "0.2.1"  # also in manifest.json; changes the cards' script address so browsers fetch the new one
SOURCE_DOMAIN = "geely_connect"  # the Geely Connect integration (YossiKon/geely-connect)

CONF_DEVICE = "device_id"
CONF_COLOR = "color"
CONF_NOTIFY = "notify_service"
CONF_CAPACITY = "capacity"
CONF_PLACES = "places"
CONF_END_MINUTES = "end_minutes"
CONF_CAPACITY_FACTOR = "capacity_factor"

DEFAULT_CAPACITY = 60.22  # kWh, Geely EX5 battery (usable, as published)
DEFAULT_END_MINUTES = 3  # a charge ends this long after power and charger stop
DEFAULT_CAPACITY_FACTOR = 1.0
# A trip ends when the odometer and trip meter stop for this long with the car parked (park brake or engine off);
# then the arrival GPS is awaited up to ARRIVAL_WAIT. Trips shorter than MIN_TRIP_KM are not recorded.
TRIP_END_SECONDS = 300
ARRIVAL_WAIT = 180
MIN_TRIP_KM = 0.3

STORAGE_VERSION = 1
SIGNAL_UPDATE = f"{DOMAIN}_update_{{}}"  # formatted with the entry id
EVENT_CHARGE_FINISHED = f"{DOMAIN}_charge_finished"
EVENT_TRIP_FINISHED = f"{DOMAIN}_trip_finished"
FRONTEND_URL = f"/{DOMAIN}"  # cards and car pictures

# Geely Connect unique ids are "geely_<VIN>_<key>". The keys used here:
KEY_BATTERY = "battery"
KEY_POWER = "charge_power"  # attribute "supply" = AC or DC
KEY_CHARGER = "charger_connected"  # "Charging" while charging
KEY_ODOMETER = "total_mileage"
KEY_TRACKER = "tracker"
KEY_REPORTED = "car_reported_at"
KEY_RANGE = "range"
KEY_TRIP = "trip_meter"  # 0.1 km
KEY_PARK = "bs_park_brake_engaged"
KEY_ENGINE = "engine_state"  # "Off" when off
KEY_PACK = "pack_power"  # kW at the battery, negative while charging
SOURCE_KEYS = (KEY_BATTERY, KEY_POWER, KEY_CHARGER, KEY_ODOMETER, KEY_TRACKER, KEY_REPORTED, KEY_RANGE, KEY_TRIP,
               KEY_PARK, KEY_ENGINE, KEY_PACK)
REQUIRED_KEYS = (KEY_BATTERY, KEY_POWER, KEY_CHARGER, KEY_ODOMETER, KEY_TRACKER)
CHARGING_STATE = "Charging"

ACTION_COST = "EX5I_COST_{}"  # formatted with the first 8 characters of the entry id
ACTION_KWH = "EX5I_KWH_{}"

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".svg")
# Body color for the Geely Connect car drawing, by picture name; dark ones get light text on the body.
PAINT = {"branco-storm": "#e6e7e8", "cinza-ash": "#62666b", "prata-moon": "#b4b7bb", "preto-carbon": "#24272c"}
DARK_PAINT = ("cinza-ash", "preto-carbon")

MONTHS = {
    "pt": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
           "novembro", "dezembro"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"],
}

# Texts that do not go through Home Assistant translations (notifications, generated labels).
TEXTS = {
    "pt": {
        "month_label": "{month} de {year}",
        "this_month": "Este mês",
        "home": "Casa",
        "unknown_place": "Outro local",
        "finished_title": "EX5: recarga {kind} concluída",
        "finished": "{place}: {kwh} kWh em {duration}, bateria {b0}% → {b1}%.",
        "finished_ask": "Informe o valor pago e os kWh do eletroposto (toque e segure, ou no painel).",
        "finished_fixed": "Custo {cost} ({price}/kWh).",
        "finished_free": "Recarga grátis.",
        "inform_cost": "Informar valor pago",
        "inform_kwh": "Informar kWh do eletroposto",
        "save": "Salvar",
        "cost_title": "EX5: custo registrado",
        "cost_saved": "{cost} ({price}/kWh). No mês: {month_cost}.",
        "kwh_title": "EX5: kWh registrado",
        "kwh_saved": "{kwh} kWh do eletroposto (o carro mediu {measured}).",
        "nothing_pending": "Nenhuma recarga esperando esse dado.",
        "summary_free": "grátis",
        "summary_pending": "custo a informar",
        "hours": "{h} h {m} min",
        "minutes": "{m} min",
        "street": "Rua",
        "unknown": "desconhecido",
        "trip_summary": "{origin} → {destination} · {km} km",
        "trip_description": "Saída {start} · chegada {end} ({minutes} min) · {km} km · bateria {b0}% → {b1}%",
        "trip_consumption": " · {kwh100} kWh/100 km",
        "trip_map": "Trajeto no mapa: {link}",
    },
    "en": {
        "month_label": "{month} {year}",
        "this_month": "This month",
        "home": "Home",
        "unknown_place": "Other place",
        "finished_title": "EX5: {kind} charge finished",
        "finished": "{place}: {kwh} kWh in {duration}, battery {b0}% → {b1}%.",
        "finished_ask": "Enter the amount paid and the station's kWh (long-press, or on the dashboard).",
        "finished_fixed": "Cost {cost} ({price}/kWh).",
        "finished_free": "Free charge.",
        "inform_cost": "Enter amount paid",
        "inform_kwh": "Enter station kWh",
        "save": "Save",
        "cost_title": "EX5: cost saved",
        "cost_saved": "{cost} ({price}/kWh). This month: {month_cost}.",
        "kwh_title": "EX5: kWh saved",
        "kwh_saved": "{kwh} kWh from the station (the car measured {measured}).",
        "nothing_pending": "No charge is waiting for this.",
        "summary_free": "free",
        "summary_pending": "cost pending",
        "hours": "{h} h {m} min",
        "minutes": "{m} min",
        "street": "Street",
        "unknown": "unknown",
        "trip_summary": "{origin} → {destination} · {km} km",
        "trip_description": "Left {start} · arrived {end} ({minutes} min) · {km} km · battery {b0}% → {b1}%",
        "trip_consumption": " · {kwh100} kWh/100 km",
        "trip_map": "Route on the map: {link}",
    },
}


def lang_key(language: str | None) -> str:
    return "pt" if (language or "").lower().startswith("pt") else "en"
