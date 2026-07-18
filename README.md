# Loop for Home Assistant

A Home Assistant custom integration that receives live data pushed from the
[Loop](https://github.com/LoopKit/Loop) iOS closed-loop insulin delivery app —
glucose, insulin, carbs, pump status, therapy settings, and alerts — via a
local webhook. No cloud, no polling.

Requires the companion
[**HomeAssistantService**](https://github.com/Camji55/loop-homeassistant-service)
Loop plugin built into your Loop app (see below).

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Camji55&repository=loop-homeassistant&category=integration)

Click the badge above, or manually:

1. HACS → three-dot menu → **Custom repositories**.
2. Add `https://github.com/Camji55/loop-homeassistant` with category **Integration**.
3. Install **Loop**, then restart Home Assistant.

### Manual

Copy `custom_components/loop` into your Home Assistant `config/custom_components/`
directory and restart.

## Setup

1. **Settings → Devices & Services → Add Integration → Loop.**
2. Copy the webhook URL it shows you. Use your external HTTPS URL (Nabu Casa
   or reverse proxy) if your phone leaves home Wi-Fi.
3. In the Loop app: **Settings → Services → Add Service → Home Assistant**,
   paste the URL, tap **Test Connection**, then **Save**.

The Loop side requires building Loop with the
[HomeAssistantService](https://github.com/Camji55/loop-homeassistant-service)
plugin included in your LoopWorkspace.

## Entities

| Entity | Description |
| --- | --- |
| `sensor.loop_blood_glucose` | Current glucose (mg/dL), trend + rate attributes |
| `sensor.loop_glucose_trend` | Trend name (`flat`, `up`, `doubleDown`, …) |
| `sensor.loop_insulin_on_board` | Active insulin (U) |
| `sensor.loop_carbs_on_board` | Active carbs (g) |
| `sensor.loop_eventual_glucose` | Loop's predicted eventual glucose |
| `sensor.loop_basal_rate` | Current delivery rate (U/h) |
| `sensor.loop_pump_reservoir` | Remaining insulin (U) |
| `sensor.loop_pump_battery` | Pump battery (%) |
| `sensor.loop_last_loop_completed` | Timestamp of last successful loop cycle |
| `sensor.loop_last_carb_entry` / `sensor.loop_last_bolus` | Most recent entries |
| `sensor.loop_active_override` | Active override name or `none` |
| `sensor.loop_last_alert` | Most recent Loop/pump/CGM alert |
| `sensor.loop_last_site_change` / `last_reservoir_change` / `last_sensor_start` | Age timestamps |
| `sensor.loop_scheduled_basal_rate` / `carb_ratio` / `insulin_sensitivity` / `correction_range` | Currently-active therapy settings (full schedules as attributes) |
| `sensor.loop_max_bolus` / `sensor.loop_max_basal_rate` | Delivery limits |
| `binary_sensor.loop_closed_loop` | Closed loop enabled |
| `binary_sensor.loop_pump_suspended` | Delivery suspended |

### Events

- `loop_data_received` — fired on every push (includes raw pump events).
- `loop_alert` — fired per alert; condition on `interruption_level == critical`
  for urgent-low automations.

## Security

The webhook ID is the only secret: anyone with the URL can push data (but not
read anything). Use HTTPS externally. This integration only receives data —
it cannot bolus, change settings, or otherwise control Loop.

## Disclaimer

This is not a medical device. Do not use Home Assistant as your primary
alerting mechanism for hypo/hyperglycemia.
