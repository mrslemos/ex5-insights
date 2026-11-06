"""EX5 Insights: charge diary, costs and monthly usage for the Geely EX5 (on top of Geely Connect)."""
from __future__ import annotations

import os

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .tracker import Ex5Tracker

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SELECT, Platform.NUMBER, Platform.IMAGE]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type Ex5ConfigEntry = ConfigEntry[Ex5Tracker]

ATTR_ENTRY = "config_entry_id"
_ENTRY = {vol.Optional(ATTR_ENTRY): cv.string}


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    _register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: Ex5ConfigEntry) -> bool:
    try:
        tracker = Ex5Tracker(hass, entry)
    except HomeAssistantError as err:
        # Geely Connect may still be loading: try again later.
        raise ConfigEntryNotReady(str(err)) from err
    await tracker.async_start()
    entry.runtime_data = tracker
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Ex5ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        await entry.runtime_data.async_stop()
    return ok


async def _async_reload(hass: HomeAssistant, entry: Ex5ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _tracker(hass: HomeAssistant, call: ServiceCall) -> Ex5Tracker:
    entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED]
    wanted = call.data.get(ATTR_ENTRY)
    if wanted:
        entries = [e for e in entries if e.entry_id == wanted]
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_entry")
    if len(entries) > 1:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="many_entries")
    return entries[0].runtime_data


def _config_file(hass: HomeAssistant, name: str) -> str:
    """A file inside the configuration folder (nothing outside it)."""
    base = os.path.realpath(hass.config.path())
    path = os.path.realpath(hass.config.path(name))
    if not path.startswith(base + os.sep):
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="bad_path")
    return path


def _register_services(hass: HomeAssistant) -> None:
    async def set_cost(call: ServiceCall) -> None:
        t = _tracker(hass, call)
        if t.set_cost(call.data["cost"], call.data.get("charge_id")) is None:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_charge")

    async def set_energy(call: ServiceCall) -> None:
        t = _tracker(hass, call)
        if t.set_station_kwh(call.data["kwh"], call.data.get("charge_id")) is None:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_charge")

    async def set_distance(call: ServiceCall) -> None:
        _tracker(hass, call).set_month_distance(call.data["month"], call.data.get("km"))

    async def delete(call: ServiceCall) -> None:
        if not _tracker(hass, call).delete_charge(call.data["charge_id"], call.data.get("restore", False)):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_charge")

    async def import_csv(call: ServiceCall) -> ServiceResponse:
        t = _tracker(hass, call)
        path = _config_file(hass, call.data["file"])

        def read() -> str:
            with open(path, encoding="utf-8-sig") as f:
                return f.read()

        try:
            text = await hass.async_add_executor_job(read)
        except OSError as err:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="bad_file",
                                         translation_placeholders={"error": str(err)}) from err
        return t.import_charges(text)

    async def export_csv(call: ServiceCall) -> ServiceResponse:
        t = _tracker(hass, call)
        path = _config_file(hass, call.data.get("file") or "ex5_insights_charges.csv")
        text = t.export_csv()

        def write() -> None:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(text)

        await hass.async_add_executor_job(write)
        return {"file": path, "charges": len(t.charges)}

    month = vol.All(cv.string, vol.Match(r"^\d{4}-\d{2}$"))
    hass.services.async_register(DOMAIN, "set_charge_cost", set_cost, vol.Schema({
        vol.Required("cost"): vol.Coerce(float), vol.Optional("charge_id"): vol.Coerce(int), **_ENTRY}))
    hass.services.async_register(DOMAIN, "set_charge_energy", set_energy, vol.Schema({
        vol.Required("kwh"): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=500)),
        vol.Optional("charge_id"): vol.Coerce(int), **_ENTRY}))
    hass.services.async_register(DOMAIN, "set_month_distance", set_distance, vol.Schema({
        vol.Required("month"): month, vol.Optional("km"): vol.Any(None, vol.Coerce(float)), **_ENTRY}))
    hass.services.async_register(DOMAIN, "delete_charge", delete, vol.Schema({
        vol.Required("charge_id"): vol.Coerce(int), vol.Optional("restore", default=False): cv.boolean, **_ENTRY}))
    hass.services.async_register(DOMAIN, "import_charges", import_csv, vol.Schema({
        vol.Required("file"): cv.string, **_ENTRY}), supports_response=SupportsResponse.OPTIONAL)
    hass.services.async_register(DOMAIN, "export_charges", export_csv, vol.Schema({
        vol.Optional("file"): cv.string, **_ENTRY}), supports_response=SupportsResponse.OPTIONAL)
