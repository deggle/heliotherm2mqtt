# Point map

Generated from `src/heliotherm2mqtt/points.py` by `tools/points_doc.py`. Do not edit by hand.

Addresses are zero-based Modbus register numbers, as in the Heliotherm Remote Control Gateway
documentation. 32-bit values span two registers, most significant word first.
Numbers are published already scaled. **W** marks points accepted as commands (when writes
are enabled). Points marked *hidden* are disabled by default in Home Assistant.

## Input registers

| Register | Point | Name | Type | Scale | Values | W | Notes |
|---|---|---|---|---|---|---|---|
| 10 | `outdoor_temperature` | Outdoor temperature | int16 | 0.1 | °C |  | not published at -50.0 or -100.0 |
| 11 | `dhw_temperature` | DHW temperature | int16 | 0.1 | °C |  | not published at -50.0 or -100.0 |
| 12 | `flow_temperature` | Flow temperature | int16 | 0.1 | °C |  | not published at -50.0 or -100.0 |
| 13 | `return_temperature` | Return temperature | int16 | 0.1 | °C |  | not published at -50.0 or -100.0 |
| 14 | `buffer_temperature` | Buffer temperature | int16 | 0.1 | °C |  | not published at -50.0 or -100.0 |
| 15 | `source_inlet_temperature` | Source inlet temperature | int16 | 0.1 | °C |  | not published at -50.0 or -100.0 |
| 16 | `source_outlet_temperature` | Source outlet temperature | int16 | 0.1 | °C |  | not published at -50.0 or -100.0 |
| 17 | `suction_line_temperature` | Suction line temperature | int16 | 0.1 | °C |  | not published at -50.0 or -100.0 |
| 18 | `evaporating_temperature` | Evaporating temperature | int16 | 0.1 | °C |  | not published at -50.0 or -100.0 |
| 19 | `condensing_temperature` | Condensing temperature | int16 | 0.1 | °C |  | not published at -50.0 or -100.0 |
| 20 | `discharge_temperature` | Discharge temperature | int16 | 0.1 | °C |  | not published at -50.0 or -100.0 |
| 21 | `low_pressure` | Low pressure | int16 | 0.1 | bar |  |  |
| 22 | `high_pressure` | High pressure | int16 | 0.1 | bar |  |  |
| 23 | `heating_circuit_pump` | Heating circuit pump | int16 | 1 | `ON` / `OFF` |  |  |
| 24 | `buffer_charging_pump` | Buffer charging pump | int16 | 1 | `ON` / `OFF` |  |  |
| 25 | `compressor` | Compressor | int16 | 1 | `ON` / `OFF` |  |  |
| 26 | `fault` | Fault | int16 | 1 | `ON` / `OFF` |  |  |
| 27 | `four_way_valve` | Four-way valve (defrost or reversing) | int16 | 1 | `ON` / `OFF` |  |  |
| 28 | `flow_rate` | Flow rate | int16 | 0.1 | L/min |  |  |
| 29 | `compressor_speed` | Compressor speed | int16 | 1 | ‰ |  |  |
| 30 | `cop` | COP | int16 | 0.1 |  |  |  |
| 31 | `fresh_water_temperature` | Fresh water temperature | int16 | 0.1 | °C |  | hidden, not published at -50.0 or -100.0 |
| 32 | `utility_release` | Utility (EVU) release | int16 | 1 | `ON` / `OFF` |  |  |
| 33 | `outdoor_temperature_delayed` | Outdoor temperature (delayed) | int16 | 0.1 | °C |  | not published at -50.0 or -100.0 |
| 34 | `return_setpoint` | Return setpoint | int16 | 0.1 | °C |  | not published at -50.0 or -100.0 |
| 35 | `mc1_flow_setpoint` | MC1 flow setpoint | int16 | 0.1 | °C |  | hidden, not published at -50.0 or -100.0 |
| 36 | `mc2_flow_setpoint` | MC2 flow setpoint | int16 | 0.1 | °C |  | hidden, not published at -50.0 or -100.0 |
| 37 | `source_pump` | Source pump or fan | int16 | 1 | `ON` / `OFF` |  |  |
| 38 | `dhw_priority` | DHW priority | int16 | 1 | `ON` / `OFF` |  |  |
| 39 | `passive_cooling_valve` | Passive cooling valve | int16 | 1 | `ON` / `OFF` |  |  |
| 40 | `expansion_valve` | Expansion valve | int16 | 1 | ‰ |  |  |
| 41 | `heat_pump_request` | Heat pump request | int16 | 1 | `none` (0), `cool` (10), `heat` (20), `dhw` (30), `external` (40) |  |  |
| 42-43 | `dhw_operating_hours` | DHW operating hours | uint32 | 1 | h |  |  |
| 44-45 | `heating_operating_hours` | Heating operating hours | uint32 | 1 | h |  |  |
| 46 | `mc1_flow_temperature` | MC1 flow temperature | int16 | 0.1 | °C |  | hidden, not published at -50.0 or -100.0 |
| 47 | `mc1_return_temperature` | MC1 return temperature | int16 | 0.1 | °C |  | hidden, not published at -50.0 or -100.0 |
| 48 | `mc2_flow_temperature` | MC2 flow temperature | int16 | 0.1 | °C |  | hidden, not published at -50.0 or -100.0 |
| 49 | `mc2_return_temperature` | MC2 return temperature | int16 | 0.1 | °C |  | hidden, not published at -50.0 or -100.0 |
| 50 | `room_temperature` | Room temperature | int16 | 0.1 | °C |  | not published at -50.0 or -100.0 |
| 60-61 | `heating_heat_energy` | Heating heat energy | uint32 | 1 | kWh |  |  |
| 62-63 | `heating_electrical_energy` | Heating electrical energy | uint32 | 1 | kWh |  |  |
| 64-65 | `dhw_heat_energy` | DHW heat energy | uint32 | 1 | kWh |  |  |
| 66-67 | `dhw_electrical_energy` | DHW electrical energy | uint32 | 1 | kWh |  |  |
| 68-69 | `total_electrical_energy` | Total electrical energy | uint32 | 1 | kWh |  |  |
| 70-71 | `electrical_power` | Electrical power | uint32 | 1 | W |  |  |
| 72-73 | `total_heat_energy` | Total heat energy | uint32 | 1 | kWh |  |  |
| 74-75 | `heat_output` | Heat output | uint32 | 0.1 | kW |  |  |

## Holding registers

| Register | Point | Name | Type | Scale | Values | W | Notes |
|---|---|---|---|---|---|---|---|
| 100 | `operating_mode` | Operating mode | uint16 | 1 | `off` (0), `auto` (1), `cool` (2), `summer` (3), `continuous` (4), `decrease` (5), `holiday` (6), `party` (7) | W |  |
| 101 | `room_setpoint` | Room setpoint | int16 | 0.1 | °C, 10 to 25 | W |  |
| 102 | `return_setpoint_value` | Return/buffer target override | int16 | 0.1 | °C, 5 to 65 | W |  |
| 103 | `return_setpoint_active` | Return/buffer target override active | uint16 | 1 | `ON` / `OFF` | W |  |
| 104 | `cooling_return_minimum` | Cooling return minimum | int16 | 0.1 | °C |  | hidden |
| 105 | `dhw_setpoint` | DHW setpoint | int16 | 0.1 | °C, 5 to 65 | W |  |
| 107 | `mc1_operating_mode` | MC1 operating mode | uint16 | 1 | `off` (0), `auto` (1), `cool` (2), `summer` (3), `continuous` (4), `decrease` (5), `holiday` (6), `party` (7) | W | hidden |
| 108 | `mc1_room_setpoint` | MC1 room setpoint | int16 | 0.1 | °C |  | hidden |
| 109 | `mc1_flow_setpoint_value` | MC1 flow setpoint override | int16 | 0.1 | °C |  | hidden |
| 110 | `mc1_flow_setpoint_active` | MC1 flow setpoint override active | uint16 | 1 | `ON` / `OFF` |  | hidden |
| 111 | `mc1_cooling_flow_minimum` | MC1 cooling flow minimum | int16 | 0.1 | °C |  | hidden |
| 112 | `mc2_operating_mode` | MC2 operating mode | uint16 | 1 | `off` (0), `auto` (1), `cool` (2), `summer` (3), `continuous` (4), `decrease` (5), `holiday` (6), `party` (7) | W | hidden |
| 113 | `mc2_room_setpoint` | MC2 room setpoint | int16 | 0.1 | °C |  | hidden |
| 114 | `mc2_flow_setpoint_value` | MC2 flow setpoint override | int16 | 0.1 | °C |  | hidden |
| 115 | `mc2_flow_setpoint_active` | MC2 flow setpoint override active | uint16 | 1 | `ON` / `OFF` |  | hidden |
| 116 | `mc2_cooling_flow_minimum` | MC2 cooling flow minimum | int16 | 0.1 | °C |  | hidden |
| 117 | `pv_request` | PV request | uint16 | 1 | `ON` / `OFF` |  | hidden |
| 118 | `pv_heat_offset` | PV heating offset | uint16 | 0.1 | K |  | hidden |
| 119 | `pv_cool_offset` | PV cooling offset | uint16 | 0.1 | K |  | hidden |
| 120 | `mc1_pv_heat_offset` | MC1 PV heating offset | uint16 | 0.1 | K |  | hidden |
| 121 | `mc1_pv_cool_offset` | MC1 PV cooling offset | uint16 | 0.1 | K |  | hidden |
| 122 | `mc2_pv_heat_offset` | MC2 PV heating offset | uint16 | 0.1 | K |  | hidden |
| 123 | `mc2_pv_cool_offset` | MC2 PV cooling offset | uint16 | 0.1 | K |  | hidden |
| 124 | `dhw_normal_maximum` | DHW normal maximum | uint16 | 0.1 | °C |  | hidden |
| 125 | `power_input_request` | Power input request | uint16 | 1 | W |  | hidden |
| 126 | `compressor_speed_request` | Compressor speed request | int16 | 1 | ‰ |  | hidden |
| 127 | `external_request` | External request | uint16 | 1 | `ON` / `OFF` |  | hidden |
| 128 | `clear_error` | Clear error | uint16 | 1 | `ON` / `OFF` |  | hidden |
| 129 | `outdoor_temperature_value` | Outdoor temperature override | int16 | 0.1 | °C |  | hidden, not published at -50.0 or -100.0 |
| 130 | `outdoor_temperature_active` | Outdoor temperature override active | uint16 | 1 | `ON` / `OFF` |  | hidden |
| 131 | `buffer_temperature_value` | Buffer temperature override | int16 | 0.1 | °C |  | hidden, not published at -50.0 or -100.0 |
| 132 | `buffer_temperature_active` | Buffer temperature override active | uint16 | 1 | `ON` / `OFF` |  | hidden |
| 133 | `dhw_temperature_value` | DHW temperature override | int16 | 0.1 | °C |  | hidden, not published at -50.0 or -100.0 |
| 134 | `dhw_temperature_active` | DHW temperature override active | uint16 | 1 | `ON` / `OFF` |  | hidden |
| 135 | `hc_heat_limit` | Heating curve outdoor limit | int16 | 0.1 | °C, 10 to 30 | W |  |
| 136 | `hc_return_at_heat_limit` | Heating curve at outdoor limit | int16 | 0.1 | °C, 15 to 55 | W |  |
| 137 | `hc_return_at_0c` | Heating curve at 0 °C | int16 | 0.1 | °C, 15 to 55 | W |  |
| 138 | `hc_return_at_minus_15c` | Heating curve at -15 °C | int16 | 0.1 | °C, 15 to 55 | W |  |
| 139 | `mc1_heat_limit` | MC1 heat limit | int16 | 0.1 | °C |  | hidden |
| 140 | `mc1_return_at_heat_limit` | MC1 return at heat limit | int16 | 0.1 | °C |  | hidden |
| 141 | `mc1_return_at_0c` | MC1 return at 0 °C | int16 | 0.1 | °C |  | hidden |
| 142 | `mc1_return_at_minus_15c` | MC1 return at -15 °C | int16 | 0.1 | °C |  | hidden |
| 143 | `mc2_heat_limit` | MC2 heat limit | int16 | 0.1 | °C |  | hidden |
| 144 | `mc2_return_at_heat_limit` | MC2 return at heat limit | int16 | 0.1 | °C |  | hidden |
| 145 | `mc2_return_at_0c` | MC2 return at 0 °C | int16 | 0.1 | °C |  | hidden |
| 146 | `mc2_return_at_minus_15c` | MC2 return at -15 °C | int16 | 0.1 | °C |  | hidden |
| 147 | `second_stage_hand_value` | Second stage override | int16 | 1 | `ON` / `OFF` |  | hidden |
| 148 | `second_stage_hand_active` | Second stage override active | uint16 | 1 | `ON` / `OFF` |  | hidden |
| 149 | `utility_release_hand_value` | Utility release override | int16 | 1 | `ON` / `OFF` |  | hidden |
| 150 | `utility_release_hand_active` | Utility release override active | int16 | 1 | `ON` / `OFF` |  | hidden |
| 151 | `tf22_hand_value` | TF22 override | int16 | 1 |  |  | hidden |
| 152 | `tf22_hand_active` | TF22 override active | uint16 | 1 | `ON` / `OFF` |  | hidden |
