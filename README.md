# EX5 Insights

[Português](README.pt-BR.md)

Charge diary, costs and monthly usage for the **Geely EX5** in Home Assistant.

It works on top of [Geely Connect](https://github.com/YossiKon/geely-connect), which talks to the car. EX5 Insights
watches the car and keeps what Geely Connect does not: every charge, where it happened, what it cost, and the month
by month numbers.

> Unofficial community project. Not affiliated with or endorsed by Geely.

## What you get

- **Charge diary.** Every charge is recorded on its own: start, end, AC or DC, place, battery before and after, kWh,
  minutes and odometer. It keeps working through Home Assistant restarts: the stretch without readings is estimated
  from the charging power and the battery rise.
- **Cost by place.** You set your charging places on a map, each with a rule:
  - **Free**: solar, parents' house, an office that pays for it.
  - **Fixed price per kWh**: e.g. the grid fee you still pay with solar.
  - **Ask the amount paid**: public chargers. Everything outside your places asks, too.

  To enter the amount paid and the station's kWh, use the dashboard fields or the notification (the text field in
  the notification works on iPhone). The station's kWh become the charge's official energy, because that is what you
  paid for.
- **Month view.** A month selector with distance, charges (AC/DC), kWh, cost, consumption (kWh/100 km), cost per km
  and a table of the month's charges (day, time, kWh, price per kWh, total).
- **Monthly charts** of kWh (AC and DC) and cost, from the diary, so imported charges show up too.
- **Import** your old charges from a spreadsheet (CSV), and **export** the diary.
- **Your car's picture** in the color you choose.
- English and Portuguese (Brazil).

## Requirements

- Home Assistant 2025.10 or newer.
- [Geely Connect](https://github.com/YossiKon/geely-connect) installed and working, with the car's sensors enabled.
- For notifications: the Home Assistant app on your phone.

## Install

1. In HACS: ⋮ > **Custom repositories** > add `https://github.com/mrslemos/ex5-insights` as **Integration**.
2. Install **EX5 Insights** and restart Home Assistant.
3. **Settings > Devices & services > Add integration > EX5 Insights**, then choose your car, color and phone.
4. On the integration, open **Configure > Add a charging place** for each place you charge.
5. Create a dashboard: **Settings > Dashboards > Add dashboard**. Open it, then **⋮ > Edit > ⋮ > Raw
   configuration editor**, and paste [`dashboards/ex5_insights.en.yaml`](dashboards/ex5_insights.en.yaml).

## Entities

| Entity | What it is |
|---|---|
| `select.ex5_month` | Month shown by the month sensors and the table |
| `sensor.ex5_month_distance` | km in the month |
| `sensor.ex5_month_charges` | Charges in the month (attributes `charges_ac`, `charges_dc`) |
| `sensor.ex5_month_energy` | kWh in the month (attributes `kwh_ac`, `kwh_dc`) |
| `sensor.ex5_month_cost` | Cost in the month (attribute `pending`: charges still without an amount) |
| `sensor.ex5_month_consumption` | kWh/100 km (from 20 km in the month) |
| `sensor.ex5_month_cost_per_km` | Cost per km (from 20 km in the month) |
| `sensor.ex5_month_table` | Number of charges; attributes `rows` and `total` feed the table |
| `sensor.ex5_last_charge` | Summary of the last charge |
| `sensor.ex5_session_energy` | kWh of the charge in progress |
| `binary_sensor.ex5_charging` | A charge is in progress |
| `number.ex5_pending_cost` | Type the amount paid of the latest charge waiting for it |
| `number.ex5_pending_station_kwh` | Type the station's kWh of the latest paid charge |
| `image.ex5_car` | Picture of the car (if there is an image for the chosen color) |

Long-term statistics `ex5_insights:energy_ac`, `ex5_insights:energy_dc` and `ex5_insights:cost` feed the charts.

The event `ex5_insights_charge_finished` fires at the end of each charge (kind, place, kWh, cost, minutes, battery),
for your own automations.

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

## How a charge is detected

- It **starts** when the charger reports "Charging" or the power goes above 0.3 kW.
- **AC or DC** comes from Geely Connect's `supply` attribute, ignored during the first 90 s, because the first
  readings of an AC charge sometimes come from the battery side and say DC.
- The **energy** is the charging power added up over time. Stretches without readings (Home Assistant restarting,
  the car reporting minutes after the charge began) are estimated from the power before and after, and capped by
  the battery rise × capacity. With no power at all, it uses the battery rise × capacity.
- It **ends** after 3 minutes (adjustable) without power and with the charger stopped.

## Privacy

Everything stays in your Home Assistant (`.storage/ex5_insights.<id>`). The places' coordinates are not exposed in
entity attributes. Nothing is sent anywhere.

## License

MIT. Car pictures: do not use official photos or the Geely logo.
