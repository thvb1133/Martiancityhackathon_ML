"""Pack the daily series the Sol Zero Console draws into marsdata.js.

Writes public/sol-zero-console/marsdata.js. Everything the console animates
(solar curve, storm step, wind rose, terrain heatmap, cabin CO2) comes from
here, so a change to the packs propagates to the demo.

After this file updates, rebuild the Next.js inspect payload:

    node scripts/export-settlement-json.mjs

Run:  python ml/settlement/export_console_data.py
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

import physics as P
from paths import CONSOLE, TRACK_A, TRACK_B, TRACK_B2, TRACK_C, ensure_out, pack

TERRAIN_CODES = {"regolith_plain": 0, "rock_field": 1, "crater_floor": 2, "crater_rim": 3,
                 "dune_field": 4, "dust_pit": 5, "lava_tube_entrance": 6}


def main() -> None:
    ensure_out()
    a = pd.read_csv(pack(TRACK_A) / "emars_settlement_hourly_730sol.csv")
    a["ws"] = np.hypot(a.wind_u_ms, a.wind_v_ms)
    d = a.groupby("sol").agg(tau=("dust_optical_depth", "max"), tmin=("temperature_c", "min"),
                             tmax=("temperature_c", "max"), load=("habitat_thermal_load_kw_100p", "mean"),
                             wsmax=("ws", "max"))
    solar = P.daily_solar_kwh_m2(a)
    c = pd.read_csv(pack(TRACK_C) / "mars500_eclss_scaled_100p_730d.csv")
    t = pd.read_csv(pack(TRACK_B2) / "terrain_grid.csv").sort_values(["grid_y", "grid_x"])
    b = pd.read_csv(pack(TRACK_B) / "logistics_duty_cycle_100p_730sol.csv")
    out = {
        "tau": d.tau.round(2).tolist(), "tmin": d.tmin.round(1).tolist(), "tmax": d.tmax.round(1).tolist(),
        "load": d.load.round(1).tolist(), "solkwh": solar.round(2).tolist(), "wsmax": d.wsmax.round(1).tolist(),
        "rose_all": P.wind_rose(a.wind_u_ms.values, a.wind_v_ms.values),
        "rose_strong": P.wind_rose(a.wind_u_ms.values, a.wind_v_ms.values, 15.0),
        "hourT": a.groupby("hour").temperature_c.mean().round(1).tolist(),
        "co2": c.cabin_co2_ppm_proxy.tolist(), "vent": c.greenhouse_ventilation_m3_per_h.tolist(),
        "wmake": c.net_water_makeup_kg.round(1).tolist(), "o2make": c.net_o2_makeup_kg.round(1).tolist(),
        "solav": c.solar_availability.round(2).tolist(),
        "grid_e": t.traversal_energy_wh_per_m.round(2).tolist(), "grid_h": t.hazard_prob.round(2).tolist(),
        "grid_t": t.terrain_type.map(TERRAIN_CODES).fillna(0).astype(int).tolist(),
        "risk": b.groupby("sol").terrain_risk_score.mean().round(3).tolist(),
    }
    js = "const DATA=" + json.dumps(out, separators=(",", ":")) + ";"
    (CONSOLE / "marsdata.js").write_text(js)
    print(f"wrote {CONSOLE / 'marsdata.js'} ({len(js) // 1024} KB)")


if __name__ == "__main__":
    main()
