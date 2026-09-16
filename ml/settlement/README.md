# Settlement decision models

Everything behind the **Sol Zero Console** demo (`public/sol-zero-console/`): the
numbers on each decision card, the two trained-model decisions, and the data file
the site animates. Track A (Architecture) with Pack B and C inputs.

## Run it

```bash
python ml/settlement/run_all.py
```

That clones the organiser packs into `data/raw/official-packs/` (gitignored), runs the
analysis, trains the models, and rewrites `public/sol-zero-console/marsdata.js`.
Already have the packs somewhere? `MARS_PACKS=/path/to/guided-packs python ml/settlement/run_all.py`.

Needs the `ml/requirements.txt` env (pandas, scikit-learn, lightgbm, joblib).

Then rebuild the compact file the Next.js inspect page reads:

```bash
node scripts/export-settlement-json.mjs
```

That writes `public/data/settlement.json` from `marsdata.js`. `pnpm dev`, then open a
site such as <http://localhost:3000/site/jezero> for the main report, or
<http://localhost:3000/sol-zero-console/> for the ten-card walkthrough.

## What is ML and what is not

Be exact about this on stage. The headline figures on the cards are **descriptive
statistics and closed-form physics**, not model predictions. The two learned decisions
sit on top of them.

| File | Kind | What it produces |
| --- | --- | --- |
| `analyse_packs.py` | pandas + physics | every card figure: solar per sol, storm onset step, heating loads, wind rose, O2 / water / food rates, battery bridge mass, dose vs depth table. Writes `data/processed/settlement_summary.json` |
| `physics.py` | closed-form models | Beer–Lambert sky model, GCR dose vs regolith cover, thermal skin depth, overburden vs cabin pressure, wind dynamic pressure, storm battery bridge, demand budget. Every constant named |
| `train_terrain_cost.py` | **ML decision 1** | LightGBM cell cost and hazard regressors on the 60×60 grid, a route success classifier on `routes.csv`, and Dijkstra over the *predicted* cost surface vs a naive straight line. Decides where to dig and how the haulers drive |
| `train_storm_models.py` | **ML decision 2** | storm-mode detector from thermal / wind / pressure sensors only (no dust input), heating-load regressor, cabin CO2 regressor, next-day water makeup forecast. Decides whether a buried habitat can trip storm mode without an optical sensor |
| `export_console_data.py` | data packaging | `marsdata.js` for the console |
| `scripts/export-settlement-json.mjs` | data packaging | `public/data/settlement.json` for the Next.js inspect page |
| `fetch_packs.py` | data | shallow clone of the organiser repo |

## Results (5-fold CV, 15 Sept 2026)

| Model | Score | Read it as |
| --- | --- | --- |
| Cell energy Wh/m | R² 0.99, MAE 0.05 Wh/m | recovers the generator's rule; slope and rock density dominate |
| Cell hazard | R² 0.98 | same |
| Route success | ROC AUC 0.995, base rate 0.64 | vehicle plus route stats separate success cleanly |
| Planned vs naive route | 2,283 Wh vs 2,886 Wh | both exceed the swarm builder's 1,200 Wh pack, so charging waypoints are mandatory either way |
| Storm detector, no dust input | AUC 1.00, trips sol 180 with zero lag | wind and temperature anomaly alone identify storm mode in this pack |
| Heating load | R² 0.999 | load column is a deterministic function of weather in the pack |
| Cabin CO2 | R² 0.95, MAE 20 ppm | proxy is mild; see KNOWN_ISSUES |
| Water makeup next day | MAE 0.35 kg vs 1.0 kg persistence | lagged storm flags carry the signal |

Full numbers: `data/processed/settlement_ml_metrics.json` after a run.

**Caveat that must be said out loud.** Packs A and C are generator output shaped like Mars,
and B2 is fully synthetic. Near-perfect scores mean the models learned the generator, not
the planet. The scores are useful for ranking options and checking design rules, not for
claiming forecast skill on real Mars weather.

## The ten decisions

| Sol | Decision | Backed by |
| --- | --- | --- |
| −700 | Site: ice at mid-latitude over solar at 18° N | A solar 3.49 kWh/m²/sol, C makeup 28 kg/day, SWIM ice prior |
| 0 | Power: fission baseload plus solar | A storm solar 0.11 kWh/m²/sol; 2,200 MWh bridge = ~15,000 t of cells |
| 5–30 | Dig on the regolith plain | B2 1.45 vs 3.02 Wh/m, hazard 0.10 vs 0.29, learned cost surface |
| 30 | Cut-and-cover 3–5 m with anchors | dose 160 → 7 mSv/yr, skin depth 0.09 / 2.4 m, uplift 70 − 18 kPa |
| 30–300 | Power → volume → water → food | C 134 t food, 5–10 k m³ volume, swarm builder rate |
| 60 | Airlocks SW, dust fences NE | A 97 % of >15 m/s winds toward NE, q max 4.8 Pa |
| 180 | Zero-warning storm trip | A τ 0.26 → 3.0 in one sol; learned detector trips sol 180 |
| 700 | Closed water / O2, imported food | C 89 kg O2, 355 kg water, 183 kg food per day |
| 700–900 | Fibre light pipes over PV → LED | 875 kW LED for 3,500 m² vs 230 kW rest of base |
| 880 | Seal, shed, wait | C CO2 870 → 1,160 ppm, water makeup 33 kg/day, B risk 0.73 |

Sources: [melaniepreen/mars-sim-girlswhomlphysicsx-hack](https://github.com/melaniepreen/mars-sim-girlswhomlphysicsx-hack),
its `CREDITS.txt` and `KNOWN_ISSUES.txt`. External priors: Curiosity RAD dose rate, NASA ECLSS
per-person rates, NASA habitable-volume standard, SWIM ice mapping, MER dust settling rate.
