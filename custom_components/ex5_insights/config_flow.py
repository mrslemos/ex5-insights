"""Setup in the UI: pick the car, then (in Configure) the color, phone, battery and charging places."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import selector as sel

from .const import (
    CONF_CAPACITY, CONF_COLOR, CONF_DEVICE, CONF_END_MINUTES, CONF_NOTIFY, CONF_PLACES, DEFAULT_CAPACITY,
    DEFAULT_END_MINUTES, DOMAIN, REQUIRED_KEYS, SOURCE_DOMAIN,
)
from .core import RULES
from .image import list_colors
from .tracker import resolve_entities


def _notify_services(hass: HomeAssistant) -> list[str]:
    skip = {"notify", "send_message", "persistent_notification"}
    return sorted(f"notify.{s}" for s in hass.services.async_services_for_domain("notify") if s not in skip)


async def _settings_schema(hass: HomeAssistant, current: dict) -> vol.Schema:
    colors = await hass.async_add_executor_job(list_colors)
    fields: dict = {}
    if colors:
        fields[vol.Optional(CONF_COLOR, description={"suggested_value": current.get(CONF_COLOR)})] = \
            sel.SelectSelector(sel.SelectSelectorConfig(
                options=[sel.SelectOptionDict(value=c, label=" ".join(w.capitalize() for w in c.replace("_", "-").split("-")))
                         for c in colors],
                mode=sel.SelectSelectorMode.DROPDOWN))
    services = _notify_services(hass)
    fields[vol.Optional(CONF_NOTIFY, description={"suggested_value": current.get(CONF_NOTIFY)})] = \
        sel.SelectSelector(sel.SelectSelectorConfig(options=services, mode=sel.SelectSelectorMode.DROPDOWN,
                                                    custom_value=True))
    fields[vol.Required(CONF_CAPACITY, default=current.get(CONF_CAPACITY, DEFAULT_CAPACITY))] = \
        sel.NumberSelector(sel.NumberSelectorConfig(min=30, max=120, step=0.01, unit_of_measurement="kWh",
                                                    mode=sel.NumberSelectorMode.BOX))
    fields[vol.Required(CONF_END_MINUTES, default=current.get(CONF_END_MINUTES, DEFAULT_END_MINUTES))] = \
        sel.NumberSelector(sel.NumberSelectorConfig(min=1, max=30, step=1, unit_of_measurement="min",
                                                    mode=sel.NumberSelectorMode.BOX))
    return vol.Schema(fields)


class Ex5ConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        reg = dr.async_get(self.hass)
        cars = [d for d in reg.devices.values()
                if any(e.domain == SOURCE_DOMAIN for e in self._entries_of(d))]
        if not cars:
            return self.async_abort(reason="no_car")
        errors: dict[str, str] = {}
        if user_input is not None:
            entities = resolve_entities(self.hass, user_input[CONF_DEVICE])
            if any(k not in entities for k in REQUIRED_KEYS):
                errors["base"] = "entities_missing"
            else:
                await self.async_set_unique_id(user_input[CONF_DEVICE])
                self._abort_if_unique_id_configured()
                device = reg.async_get(user_input[CONF_DEVICE])
                title = (device.name_by_user or device.name) if device else "Geely EX5"
                options = {k: v for k, v in user_input.items() if k != CONF_DEVICE and v not in (None, "")}
                options[CONF_PLACES] = []
                return self.async_create_entry(title=title, data={CONF_DEVICE: user_input[CONF_DEVICE]},
                                               options=options)
        schema = vol.Schema({
            vol.Required(CONF_DEVICE): sel.DeviceSelector(sel.DeviceSelectorConfig(integration=SOURCE_DOMAIN)),
        }).extend((await _settings_schema(self.hass, {})).schema)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    def _entries_of(self, device: dr.DeviceEntry) -> list[ConfigEntry]:
        return [e for e in (self.hass.config_entries.async_get_entry(i) for i in device.config_entries) if e]

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return Ex5OptionsFlow()


class Ex5OptionsFlow(OptionsFlow):
    """Menu: settings, add / edit / remove charging places."""

    def __init__(self) -> None:
        self._editing: int | None = None

    @property
    def _opts(self) -> dict:
        return dict(self.config_entry.options)

    @property
    def _places(self) -> list[dict]:
        return list(self._opts.get(CONF_PLACES, []))

    def _save(self, **changes) -> ConfigFlowResult:
        return self.async_create_entry(data={**self._opts, **changes})

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        menu = ["settings", "add_place"]
        if self._places:
            menu += ["edit_place", "remove_place"]
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_settings(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            opts = {k: v for k, v in self._opts.items() if k not in (CONF_COLOR, CONF_NOTIFY)}
            opts.update({k: v for k, v in user_input.items() if v not in (None, "")})
            return self.async_create_entry(data=opts)
        return self.async_show_form(step_id="settings", data_schema=await _settings_schema(self.hass, self._opts))

    def _place_schema(self, p: dict) -> vol.Schema:
        home = {"latitude": self.hass.config.latitude, "longitude": self.hass.config.longitude, "radius": 300}
        loc = {"latitude": p["latitude"], "longitude": p["longitude"], "radius": p.get("radius", 300)} if p else home
        rule = sel.SelectSelector(sel.SelectSelectorConfig(options=list(RULES), translation_key="rule",
                                                           mode=sel.SelectSelectorMode.LIST))
        tariff = sel.NumberSelector(sel.NumberSelectorConfig(min=0, max=100, step=0.000001,
                                                             mode=sel.NumberSelectorMode.BOX))
        return vol.Schema({
            vol.Required("name", default=p.get("name", "")): sel.TextSelector(),
            vol.Required("location", default=loc): sel.LocationSelector(sel.LocationSelectorConfig(radius=True)),
            vol.Required("rule", default=p.get("rule", "free")): rule,
            vol.Optional("tariff", default=p.get("tariff", 0)): tariff,
            vol.Required("dc_rule", default=p.get("dc_rule", "ask")): rule,
            vol.Optional("dc_tariff", default=p.get("dc_tariff", 0)): tariff,
        })

    @staticmethod
    def _place_from_input(user_input: dict) -> dict:
        loc = user_input["location"]
        return {
            "name": user_input["name"].strip(),
            "latitude": loc["latitude"], "longitude": loc["longitude"], "radius": loc.get("radius", 300),
            "rule": user_input["rule"], "tariff": float(user_input.get("tariff") or 0),
            "dc_rule": user_input["dc_rule"], "dc_tariff": float(user_input.get("dc_tariff") or 0),
        }

    async def async_step_add_place(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None and user_input["name"].strip():
            return self._save(**{CONF_PLACES: self._places + [self._place_from_input(user_input)]})
        return self.async_show_form(step_id="add_place", data_schema=self._place_schema({}))

    async def async_step_edit_place(self, user_input=None) -> ConfigFlowResult:
        names = [p["name"] for p in self._places]
        if user_input is not None:
            self._editing = names.index(user_input["place"])
            return await self.async_step_place_form()
        return self.async_show_form(step_id="edit_place", data_schema=vol.Schema({
            vol.Required("place"): sel.SelectSelector(sel.SelectSelectorConfig(options=names))}))

    async def async_step_place_form(self, user_input=None) -> ConfigFlowResult:
        places = self._places
        if user_input is not None and self._editing is not None:
            places[self._editing] = self._place_from_input(user_input)
            return self._save(**{CONF_PLACES: places})
        return self.async_show_form(step_id="place_form", data_schema=self._place_schema(places[self._editing]))

    async def async_step_remove_place(self, user_input=None) -> ConfigFlowResult:
        names = [p["name"] for p in self._places]
        if user_input is not None:
            gone = set(user_input.get("places", []))
            return self._save(**{CONF_PLACES: [p for p in self._places if p["name"] not in gone]})
        return self.async_show_form(step_id="remove_place", data_schema=vol.Schema({
            vol.Optional("places", default=[]): sel.SelectSelector(
                sel.SelectSelectorConfig(options=names, multiple=True))}))
