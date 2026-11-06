"""Constants for EX5 Insights."""
from __future__ import annotations

DOMAIN = "ex5_insights"
SOURCE_DOMAIN = "geely_connect"  # the Geely Connect integration (YossiKon/geely-connect)

CONF_DEVICE = "device_id"
CONF_COLOR = "color"
CONF_NOTIFY = "notify_service"
CONF_CAPACITY = "capacity"
CONF_PLACES = "places"
CONF_END_MINUTES = "end_minutes"

DEFAULT_CAPACITY = 60.22  # kWh, Geely EX5 battery (usable, as published)
DEFAULT_END_MINUTES = 3  # a charge ends this long after power and charger stop

STORAGE_VERSION = 1
SIGNAL_UPDATE = f"{DOMAIN}_update_{{}}"  # formatted with the entry id
EVENT_CHARGE_FINISHED = f"{DOMAIN}_charge_finished"

# Geely Connect unique ids are "geely_<VIN>_<key>". The keys used here:
KEY_BATTERY = "battery"
KEY_POWER = "charge_power"  # attribute "supply" = AC or DC
KEY_CHARGER = "charger_connected"  # "Charging" while charging
KEY_ODOMETER = "total_mileage"
KEY_TRACKER = "tracker"
KEY_REPORTED = "car_reported_at"
KEY_RANGE = "range"
SOURCE_KEYS = (KEY_BATTERY, KEY_POWER, KEY_CHARGER, KEY_ODOMETER, KEY_TRACKER, KEY_REPORTED, KEY_RANGE)
REQUIRED_KEYS = (KEY_BATTERY, KEY_POWER, KEY_CHARGER, KEY_ODOMETER, KEY_TRACKER)
CHARGING_STATE = "Charging"

ACTION_COST = "EX5I_COST_{}"  # formatted with the first 8 characters of the entry id
ACTION_KWH = "EX5I_KWH_{}"

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".svg")

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
    },
    "en": {
        "month_label": "{month} {year}",
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
    },
}


def lang_key(language: str | None) -> str:
    return "pt" if (language or "").lower().startswith("pt") else "en"
