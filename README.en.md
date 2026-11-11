# EX5 Insights

[Português](README.md)

Charges, costs, trips, real range and battery health for the **Geely EX5** in Home Assistant, with a ready-made
dashboard.

It works on top of [Geely Connect](https://github.com/YossiKon/geely-connect), which talks to the car. EX5 Insights
watches the car and keeps what Geely Connect does not: every charge and what it cost, every trip and its path, how far
the car really goes on a full battery, and how the battery holds up over time.

> Unofficial community project. Not affiliated with or endorsed by Geely.

## What you get

A dashboard with four tabs:

- **Overview**: the Geely Connect car cards, already set up for your car, its picture and body color (lock, climate,
  trunk, charging, tires, doors and a top view), and a map of where the car is.
- **Usage**: month by month, distance, charges (AC/DC), kWh, cost, consumption (kWh/100 km), cost per km, a table of
  the month's charges, and monthly charts of km and kWh.
- **Range**: the **real range** from your own driving (highway, city and overall), how far the current battery goes
  at that pace, the car's own estimate, the **real battery capacity** and the **battery health**, with charts over
  time.
- **Timeline**: the exact path of the trips of any day, colored by speed, a calendar of trips, and the list of the
  month's trips with a map link for each.

Behind it:

- **Charge diary.** Every charge is recorded on its own: start, end, AC or DC, place, battery before and after, kWh,
  minutes and odometer. It keeps working through Home Assistant restarts: the stretch without readings is estimated
  from the charging power and the battery rise.
- **Cost by place.** You set your charging places on a map, each with a rule:
  - **Free**: solar, parents' house, an office that pays for it.
  - **Fixed price per kWh**: e.g. the grid fee you still pay with solar.
  - **Ask the amount paid**: public chargers. Everything outside your places asks, too.

  Enter the amount paid and the station's kWh on the dashboard or in the notification (the notification's text field
  works on iPhone). The station's kWh become the charge's official energy, because that is what you paid for.
- **Trip diary.** Every trip from one parking spot to the next: origin, destination, km, minutes, battery used, kWh,
  consumption, average and top speed, and its path on the map.
- **Place names without internet.** Outside your charging places and Home Assistant zones, a trip starts or ends in
  a **city**, found from the official boundaries of the 5,570 Brazilian municipalities; in the Federal District, in
  the **administrative region** (Taguatinga, Plano Piloto…) instead of "Brasília". Outside Brazil it shows "Street".
- **Import** old charges from a spreadsheet (CSV) and **export** the diary.
- English and Portuguese (Brazil). Pictures of the car in Branco Storm, Cinza Ash, Prata Moon and Preto Carbon.

## Requirements

- Home Assistant 2025.10 or newer.
- [Geely Connect](https://github.com/YossiKon/geely-connect) installed and working, with the car's sensors enabled.
- EX5 Insights must run **on the same Home Assistant as Geely Connect**. Geely accepts one session per account:
  signing in to the same account on a second Home Assistant (a test copy, for example) logs the first one out.
- For notifications: the Home Assistant app on your phone.

## Install

1. Add the repository:
   - **Home Assistant 2026.11 or newer:** **Settings > Marketplace**, then the option to add a repository by link
     (top right), and enter `mrslemos/ex5-insights`. It asks you to connect GitHub once.
   - **Up to 2026.10, with HACS:** ⋮ > **Custom repositories** > add `https://github.com/mrslemos/ex5-insights` as
     **Integration**.
2. Install **EX5 Insights** and restart Home Assistant.
3. **Settings > Devices & services > Add integration > EX5 Insights**, then choose your car, color and phone.
4. On the integration, open **Configure > Add a charging place** for each place you charge.
5. Create the dashboard: **Settings > Dashboards > Add dashboard**. Open it, then **⋮ > Edit > ⋮ > Raw configuration
   editor**, and paste [`dashboards/ex5_insights.en.yaml`](dashboards/ex5_insights.en.yaml)
   (in Portuguese: [`dashboards/ex5_insights.pt-BR.yaml`](dashboards/ex5_insights.pt-BR.yaml)).

The dashboard uses four small cards that come with EX5 Insights and load by themselves, with nothing else to install:
`ex5-car-card`, `ex5-map-card`, `ex5-timeline-card` and `ex5-heading`. The Overview tab also needs the cards that come
with Geely Connect. With more than one EX5, set `entity:` on the cards to that car's battery sensor
(`sensor.ex5_battery_…`) and `entry:` on the timeline card to its config entry id.

The Range tab fills in as you drive. Until your trips add up to 100 % of battery used, its numbers are a preview, and
the real capacity appears after the first charge of 20 points or more.

## Entities

| Entity | What it is |
|---|---|
| `select.ex5_month` | Month shown by the month sensors, the charge table and the trip list |
| `sensor.ex5_month_distance` | km in the month |
| `sensor.ex5_month_charges` | Charges in the month (attributes `charges_ac`, `charges_dc`) |
| `sensor.ex5_month_energy` | kWh in the month (attributes `kwh_ac`, `kwh_dc`) |
| `sensor.ex5_month_cost` | Cost in the month (attribute `pending`: charges still without an amount) |
| `sensor.ex5_month_consumption` | kWh/100 km (from 20 km in the month) |
| `sensor.ex5_month_cost_per_km` | Cost per km (from 20 km in the month) |
| `sensor.ex5_month_table` | Number of charges; attributes `rows` and `total` feed the table |
| `sensor.ex5_month_trips` | Number of trips; attribute `trips` feeds the list |
| `sensor.ex5_last_charge` | Summary of the last charge |
| `sensor.ex5_last_trip` | Summary of the last trip |
| `sensor.ex5_session_energy` | kWh of the charge in progress |
| `sensor.ex5_real_range` (`_highway`, `_city`) | km per full battery, from your trips (attributes `preview`, `km`, `battery_pct`, `trips`, `kwh_100km`) |
| `sensor.ex5_range_now` (`_highway`, `_city`) | How far the current battery goes at that pace |
| `sensor.ex5_car_range`, `sensor.ex5_car_range_full` | The car's own range estimate, now and taken to 100 % |
| `sensor.ex5_battery_capacity` | Real usable capacity, measured in the charges |
| `sensor.ex5_battery_health` | Real capacity ÷ published capacity |
| `sensor.ex5_battery`, `sensor.ex5_odometer` | Battery and odometer under fixed entity ids, for the dashboard |
| `binary_sensor.ex5_charging` | A charge is in progress |
| `binary_sensor.ex5_driving` | A trip is in progress (attribute `parked_at` when parked) |
| `calendar.ex5_trips` | One event per trip, with times, battery, consumption and the map link |
| `number.ex5_pending_cost` | Type the amount paid of the latest charge waiting for it |
| `number.ex5_pending_station_kwh` | Type the station's kWh of the latest paid charge |
| `image.ex5_car` | Picture of the car in the chosen color |

Long-term statistics `ex5_insights:energy_ac` and `ex5_insights:energy_dc` feed the kWh chart (imported charges
included); `ex5_insights:cost` is there for your own charts.

Events for your own automations: `ex5_insights_charge_finished` (kind, place, kWh, cost, minutes, battery) and
`ex5_insights_trip_finished` (origin, destination, km, minutes, battery, kWh).

## Services

| Service | What it does |
|---|---|
| `ex5_insights.set_charge_cost` | Amount paid for a charge (the latest pending one, or `charge_id`) |
| `ex5_insights.set_charge_energy` | The station's kWh for a charge |
| `ex5_insights.set_month_distance` | km of a month without odometer data (e.g. before installing) |
| `ex5_insights.import_charges` | Adds charges from a CSV in the configuration folder |
| `ex5_insights.export_charges` | Writes the diary as CSV |
| `ex5_insights.delete_charge` | Hides a charge (`restore: true` brings it back) |

### Importing old charges

Save your spreadsheet as CSV in the configuration folder (for example with the File editor add-on) and call
`ex5_insights.import_charges` with `file: charges.csv`. Columns, in English or Portuguese, in any order:

| Column | Required | Examples |
|---|---|---|
| `date` / `data` | yes | `2026-01-15`, `15/01/2026`, `2026-01-15 14:28` |
| `kwh` / `carga kwh` | yes | `42.77`, `42,77` |
| `time` / `hora` | no | `14:28` (without it, the table shows —) |
| `type` / `tipo` | no | `AC`, `DC` (without it: DC above 22 kW of `power`, else AC) |
| `cost` / `custo` / `valor total` | no | `55.18`, `R$ 55,18` (empty = amount pending) |
| `place` / `local`, `minutes` / `minutos`, `odometer` / `odômetro`, `power` / `potência kw` | no | |

Charges on the same day with the same kWh are skipped, so importing twice is safe.

## How it works

**Charges.** A charge starts when the charger reports "Charging" or the power goes above 0.3 kW, and ends after
3 minutes (adjustable) without power and with the charger stopped. AC or DC comes from Geely Connect's `supply`
attribute, ignored during the first 90 s (the first readings of an AC charge sometimes say DC). The energy is the
charging power added up over time; stretches without readings are estimated from the power before and after, capped
by the battery rise × capacity.

**Trips.** A trip starts when the odometer or the trip meter moves past where the car parked, and ends when both
stand still for 5 minutes with the car parked (park brake on or engine off), after waiting up to 3 minutes for the
arrival GPS. While driving, Geely Connect sends the position about once a minute: that is the path. Trips under
0.3 km are not recorded. The battery used × capacity gives the trip's kWh.

**Real range.** The km of the latest trips until 100 % of battery has been used, counting what the car uses while
parked (climate, losses: the battery at the end of a trip or charge minus at the start of the next one). Highway trips
are 10 km or longer with more than half of the distance at 70 km/h or more, by the GPS path (without a path: more than
30 km or an average above 60 km/h). The others are city trips, and they share the parked use in proportion to their km.

**Battery capacity.** In each charge, the energy that went into the pack (Geely Connect's `pack_power`) between the
first and the last time the percentage went up, divided by the points gained. Only charges of 20 points or more, up to
95 % (above that the battery balances and the percentage moves slowly), and not when Home Assistant restarted during
the charge. The capacity is the average of the latest three measurements, times a calibration factor (1 by default; if
an OBD2 app such as ABRP shows the battery health, factor = health × 60.22 / 100 ÷ measured capacity). Health compares
it with the published 60.22 kWh. Until the first measurement, kWh use the published capacity.

## Privacy

Everything stays in your Home Assistant; nothing is sent anywhere. The diary is in `.storage/ex5_insights.<id>` and
the paths of the trips in `ex5_insights/paths/<id>/` inside the configuration folder, and both go into Home Assistant
backups. Trip paths and map links contain positions, including where you park at home: they are shown only to users
signed in to your Home Assistant (the timeline API requires sign-in). The coordinates of your charging places are not
in the entities' attributes.

## Map data

City and region names come from public data shipped with the integration: IBGE municipal boundaries, the
[kelvins/municipios-brasileiros](https://github.com/kelvins/municipios-brasileiros) list (MIT) and the Federal
District's administrative regions (GDF, IPE-DF). Details and licenses in
[`geo/SOURCES.md`](custom_components/ex5_insights/geo/SOURCES.md).

## Development

`python3 -m unittest discover tests` runs the tests of the pure logic (no Home Assistant needed).
`python3 scripts/make_dashboards.py` writes the dashboards in both languages.

## License

MIT. Car pictures: do not use official photos or the Geely logo.
