"""Generates dashboards/ex5_insights.<lang>.yaml (run: python3 scripts/make_dashboards.py)."""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).parents[1]


def to_yaml(x, indent=0):
    pad = "  " * indent
    if isinstance(x, dict):
        out = []
        for k, v in x.items():
            if isinstance(v, (dict, list)) and v:
                out.append(f"{pad}{k}:\n{to_yaml(v, indent + 1)}")
            else:
                out.append(f"{pad}{k}: {scalar(v)}")
        return "\n".join(out)
    if isinstance(x, list):
        out = []
        for v in x:
            if isinstance(v, dict) and v:
                body = to_yaml(v, indent + 1).lstrip()
                out.append(f"{pad}- {body}")
            elif isinstance(v, list) and v:
                out.append(f"{pad}-\n{to_yaml(v, indent + 1)}")
            else:
                out.append(f"{pad}- {scalar(v)}")
        return "\n".join(out)
    return pad + scalar(x)


def scalar(v):
    if v is True:
        return "true"
    if v is False:
        return "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    if v == {}:
        return "{}"
    if v == []:
        return "[]"
    s = str(v)
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.\-/ ]*", s) and s.lower() not in ("yes", "no", "on", "off", "true", "false", "null"):
        return s
    return json.dumps(s, ensure_ascii=False)


def dash(pt):
    T = lambda en, p: p if pt else en  # noqa: E731
    pend, free = T("pending", "a informar"), T("free", "grátis")
    table = (
        "{% set e = 'sensor.ex5_month_table' %}{% set rs = state_attr(e, 'rows') or [] %}"
        "{% set t = state_attr(e, 'total') or {} %}"
        "{% if rs | count == 0 %}" + T("No charges in ", "Nenhuma recarga em ")
        + "{{ state_attr(e, 'month_label') }}.{% else %}\n"
        "<table width=\"100%\">\n"
        "<tr><th align=\"left\">" + T("Day", "Dia") + "</th><th align=\"left\">" + T("Time", "Hora") + "</th>"
        "<th align=\"right\">kWh</th><th align=\"right\">" + T("Price/kWh", "R$/kWh") + "</th>"
        "<th align=\"right\">" + T("Total", "Total R$") + "</th></tr>\n"
        "{% for x in rs %}<tr><td>{{ x.day }}</td><td>{{ x.time or '—' }}</td><td align=\"right\">{{ x.kwh }}</td>"
        "<td align=\"right\">{{ '" + pend + "' if x.pending else ('—' if x.free else x.price) }}</td>"
        "<td align=\"right\">{{ '" + pend + "' if x.pending else ('" + free + "' if x.free else x.total) }}</td></tr>\n"
        "{% endfor %}<tr><td colspan=\"2\"><b>Total</b></td><td align=\"right\"><b>{{ t.kwh }}</b></td>"
        "<td align=\"right\"><b>{{ t.price or '—' }}</b></td><td align=\"right\"><b>{{ t.total }}</b></td></tr>\n"
        "</table>{% if t.pending | default(0) > 0 %}\n\n<small>{{ t.pending }} "
        + T("charge(s) with the amount still pending, not in the total.",
            "recarga(s) com valor ainda a informar, fora do total.")
        + "</small>{% endif %}{% endif %}"
    )

    def tile(e, name, icon, color):
        return {"type": "tile", "entity": e, "name": name, "icon": icon, "color": color,
                "grid_options": {"columns": 6}}

    def waiting(entity, title, name):
        return {"type": "conditional",
                "conditions": [{"condition": "state", "entity": entity, "state_not": "unavailable"}],
                "card": {"type": "entities", "title": title, "entities": [{"entity": entity, "name": name}]}}

    trips_list = (
        "{% set e = 'sensor.ex5_month_trips' %}{% set vs = state_attr(e, 'trips') or [] %}"
        "{% set days = " + T("['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']",
                             "['seg.', 'ter.', 'qua.', 'qui.', 'sex.', 'sáb.', 'dom.']") + " %}"
        "{% if vs | count == 0 %}" + T("No trips in ", "Nenhuma viagem registrada em ")
        + "{{ (state_attr(e, 'month_label') or '') | lower }}.{% else %}{% set ns = namespace(day='') %}"
        "{% for x in vs %}{% if x.day != ns.day %}{% set ns.day = x.day %}{% set d = as_datetime(x.day) %}\n\n"
        "**{{ days[d.weekday()] }} {{ d.strftime('" + T("%m/%d", "%d/%m") + "') }}**\n{% endif %}\n"
        "{{ x.time }} · {{ x.summary }}{% if x.map %} · [" + T("map", "mapa") + "]({{ x.map }}){% endif %}  "
        "{% endfor %}{% endif %}"
    )

    def header(text):
        return {"card": {"type": "markdown", "text_only": True, "content": f"# {text}"}}

    car_view = {
        "type": "sections", "title": "Geely EX5", "path": "ex5", "icon": "mdi:car-electric", "max_columns": 2,
        "sections": [
            {"type": "grid", "cards": [
                {"type": "heading", "heading": T("Car", "Carro"), "icon": "mdi:car-electric"},
                {"type": "custom:ex5-car-card", "grid_options": {"columns": "full"}},
            ]},
            {"type": "grid", "cards": [
                {"type": "heading", "heading": T("Where it is", "Onde está"), "icon": "mdi:map-marker"},
                {"type": "custom:ex5-map-card", "grid_options": {"columns": "full", "rows": 5}},
            ]},
        ],
    }
    range_view = {
        "type": "sections", "title": T("Range", "Autonomia"), "path": T("range", "autonomia"),
        "icon": "mdi:map-marker-distance", "max_columns": 2, "header": header(T("Range", "Autonomia")),
        "sections": [
            {"type": "grid", "cards": [
                {"type": "heading", "heading": T("Full charge (100%)", "Carga cheia (100%)"), "icon": "mdi:battery"},
                tile("sensor.ex5_real_range_highway", T("Highway", "Estrada"), "mdi:highway", "blue"),
                tile("sensor.ex5_real_range_city", T("City", "Cidade"), "mdi:city-variant-outline", "green"),
                tile("sensor.ex5_real_range", T("Overall", "Geral"), "mdi:map-marker-distance", "purple"),
                tile("sensor.ex5_car_range_full", T("By the car", "Pelo carro"), "mdi:car-info", "grey"),
            ]},
            {"type": "grid", "cards": [
                {"type": "heading", "heading": T("Current charge", "Carga atual"), "icon": "mdi:battery-50",
                 "badges": [{"type": "entity", "entity": "sensor.ex5_battery", "show_icon": False}]},
                tile("sensor.ex5_range_now_highway", T("Highway", "Estrada"), "mdi:highway", "blue"),
                tile("sensor.ex5_range_now_city", T("City", "Cidade"), "mdi:city-variant-outline", "green"),
                tile("sensor.ex5_range_now", T("Overall", "Geral"), "mdi:map-marker-distance", "purple"),
                tile("sensor.ex5_car_range", T("By the car", "Pelo carro"), "mdi:car-info", "grey"),
            ]},
            {"type": "grid", "cards": [
                {"type": "heading", "heading": T("Battery", "Bateria"), "icon": "mdi:car-battery"},
                tile("sensor.ex5_battery_health", T("Health", "Saúde"), "mdi:battery-heart", "red"),
                tile("sensor.ex5_battery_capacity", T("Max. capacity", "Capacidade máx."), "mdi:battery-high", "amber"),
            ]},
            {"type": "grid", "cards": [
                {"type": "heading", "heading": T("Over time", "Ao longo do tempo"), "icon": "mdi:chart-line"},
                {"type": "statistics-graph", "title": T("Range", "Autonomia"), "chart_type": "line", "period": "week",
                 "days_to_show": 365, "stat_types": ["mean"], "hide_legend": False,
                 "grid_options": {"columns": "full"},
                 "entities": [{"entity": "sensor.ex5_real_range_highway", "name": T("Highway", "Estrada")},
                              {"entity": "sensor.ex5_real_range_city", "name": T("City", "Cidade")},
                              {"entity": "sensor.ex5_real_range", "name": T("Overall", "Geral")}]},
                {"type": "statistics-graph", "title": T("Battery health", "Saúde da bateria"), "chart_type": "line",
                 "period": "month", "days_to_show": 1095, "stat_types": ["mean"],
                 "grid_options": {"columns": "full"},
                 "entities": [{"entity": "sensor.ex5_battery_health", "name": T("Health", "Saúde")}]},
            ]},
        ],
    }
    timeline_view = {
        "type": "sections", "title": "Timeline", "path": T("trips", "viagens"), "icon": "mdi:map",
        "max_columns": 2, "header": header("Timeline"),
        "sections": [
            {"type": "grid", "cards": [
                {"type": "heading", "heading": T("Path of the day", "Rastro do dia"), "icon": "mdi:map-marker-path"},
                {"type": "custom:ex5-timeline-card", "height": 420, "grid_options": {"columns": "full"}},
            ]},
            {"type": "grid", "cards": [
                {"type": "heading", "heading": T("Trips", "Viagens"), "icon": "mdi:calendar-month"},
                {"type": "calendar", "entities": ["calendar.ex5_trips"], "initial_view": "listWeek",
                 "grid_options": {"columns": "full"}},
                {"type": "heading", "heading": T("Trips of the month", "Viagens do mês"),
                 "icon": "mdi:format-list-bulleted", "heading_style": "subtitle"},
                {"type": "tile", "entity": "select.ex5_month", "name": T("Month", "Mês"),
                 "icon": "mdi:calendar-month", "color": "blue", "hide_state": True, "vertical": False,
                 "features_position": "inline", "features": [{"type": "select-options"}],
                 "grid_options": {"columns": "full"}},
                {"type": "markdown", "grid_options": {"columns": "full"}, "content": trips_list},
            ]},
        ],
    }
    return {
        "title": "EX5",
        "views": [car_view, {
            "type": "sections", "title": T("Usage", "Uso"), "path": T("usage", "uso"),
            "icon": "mdi:chart-box-outline", "max_columns": 2,
            "sections": [
                {"type": "grid", "cards": [
                    {"type": "heading", "heading": T("Month", "Mês"), "icon": "mdi:calendar-month"},
                    {"type": "tile", "entity": "select.ex5_month", "name": T("Month", "Mês"),
                     "icon": "mdi:calendar-month", "color": "blue", "hide_state": True, "vertical": False,
                     "features_position": "inline", "features": [{"type": "select-options"}],
                     "grid_options": {"columns": "full"}},
                    tile("sensor.ex5_month_distance", "Km", "mdi:map-marker-distance", "blue"),
                    tile("sensor.ex5_month_charges", T("Charges", "Recargas"), "mdi:ev-station", "green"),
                    tile("sensor.ex5_month_energy", "kWh", "mdi:lightning-bolt", "amber"),
                    tile("sensor.ex5_month_cost", T("Cost", "Custo"), "mdi:cash", "red"),
                    tile("sensor.ex5_month_consumption", T("Consumption", "Consumo"), "mdi:speedometer", "purple"),
                    tile("sensor.ex5_month_cost_per_km", T("Cost per km", "Custo por km"), "mdi:cash-marker", "grey"),
                    waiting("number.ex5_pending_cost", T("Charge waiting for the amount paid",
                                                         "Recarga esperando o valor pago"),
                            T("Amount paid", "Valor pago")),
                    waiting("number.ex5_pending_station_kwh", T("Charge waiting for the station's kWh",
                                                                "Recarga esperando os kWh do eletroposto"),
                            T("Station kWh", "kWh do eletroposto")),
                    {"type": "heading", "heading": T("Charges of the month", "Recargas do mês"),
                     "icon": "mdi:ev-station"},
                    {"type": "markdown", "grid_options": {"columns": "full"}, "content": table},
                ]},
                {"type": "grid", "cards": [
                    {"type": "heading", "heading": T("Car", "Carro"), "icon": "mdi:car-electric"},
                    {"type": "picture-entity", "entity": "image.ex5_car", "show_name": False, "show_state": False,
                     "grid_options": {"columns": "full"}},
                    {"type": "tile", "entity": "binary_sensor.ex5_charging", "name": T("Charging", "Carregando"),
                     "grid_options": {"columns": 6}},
                    {"type": "tile", "entity": "sensor.ex5_session_energy", "name": T("This charge", "Esta recarga"),
                     "grid_options": {"columns": 6}},
                    {"type": "tile", "entity": "sensor.ex5_last_charge", "name": T("Last charge", "Última recarga"),
                     "grid_options": {"columns": "full"}},
                    {"type": "heading", "heading": T("By month", "Por mês"), "icon": "mdi:chart-bar"},
                    {"type": "statistics-graph", "title": "Km", "chart_type": "bar", "period": "month",
                     "days_to_show": 365, "stat_types": ["change"], "hide_legend": True,
                     "entities": [{"entity": "sensor.ex5_odometer", "name": "Km"}],
                     "grid_options": {"columns": "full"}},
                    {"type": "statistics-graph", "title": T("kWh charged", "kWh carregados"), "chart_type": "bar",
                     "period": "month", "days_to_show": 365, "stat_types": ["change"],
                     "entities": [{"entity": "ex5_insights:energy_ac", "name": "AC"},
                                  {"entity": "ex5_insights:energy_dc", "name": "DC"}],
                     "grid_options": {"columns": "full"}},
                    {"type": "statistics-graph", "title": T("Cost", "Custo"), "chart_type": "bar",
                     "period": "month", "days_to_show": 365, "stat_types": ["change"], "hide_legend": True,
                     "entities": [{"entity": "ex5_insights:cost", "name": T("Cost", "Custo")}],
                     "grid_options": {"columns": "full"}},
                ]},
            ],
        }, range_view, timeline_view],
    }


for lang, pt in (("en", False), ("pt-BR", True)):
    head = ("# Painel do EX5 Insights. Copie tudo e cole em Configurações > Painéis > (novo painel) > "
            "⋮ > Editor de configuração bruta.\n" if pt else
            "# EX5 Insights dashboard. Copy everything and paste it in Settings > Dashboards > (new dashboard) > "
            "⋮ > Raw configuration editor.\n")
    (ROOT / "dashboards" / f"ex5_insights.{lang}.yaml").write_text(head + to_yaml(dash(pt)) + "\n", encoding="utf-8")
print("ok")
