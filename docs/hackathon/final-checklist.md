# Final checklist

Fill this in as you lock scope, then again before the 20:35 push. Empty fields mean the demo is not ready to explain.

Event repo rules: public repo, last commit before **20:35**, README names the build, the **track**, how ML was used, and how to run the demo. 3 minutes on stage, 2 minutes Q&A.

## 1. What we shipped

- Crew name / repo: `Mangle Kuo / https://github.com/ghcpuman902/mars-hackathon-2026`
- One-sentence product: `Pick a NASA landing area, then read a site report that sizes radiation cover, quake, wind, and burial depth, and shows the pack storm series, dig cost, and makeup water.`
- **Track (pick one):**
  - [x] A Architecture
  - [ ] B Vehicles & Mobility
  - [ ] C Life Support & Resource Systems
- One ML decision (better than a guess): `Physics rules still size bury depth from elevation and ice. The inspect page also shows two learned pack decisions: a storm detector that trips sol 180 from wind and temperature (no dust sensor), and a terrain-cost surface that says dig on the plain (1.45 vs 3.02 Wh/m).`
  What the model or rule outputs, and what a human then builds or does with that output.
- Non-goals (will not mention on stage): `Trained radiation or seismic models, a full cave catalog, geothermal power, simulated lava-tube clusters in the 3D mesh.`

Shared scenario, unless you deliberately left it: **100 people**, **730 sols**, dust storm **sols 180–260**.

## 2. Data we used

Tick only what actually fed the demo. Write the file path. If a pack is simulated, say so in the README and on stage.

### Official guided packs

See [official-packs.md](./official-packs.md). Discovery notes: [A](./track-a-emars.md), [B](./track-b-ai4mars.md), [B2](./track-b2-mobility.md), [C](./track-c-eclss.md).

| Used | Pack | Path | Real or simulated | What we took from it |
| --- | --- | --- | --- | --- |
| [x] | A EMARS weather | `data/raw/official-packs/extracted/track-a-architecture-emars/` | Simulated, EMARS-informed | `Hourly wind for pressure; daily solar, optical depth, and heating on the inspect sparkline` |
| [ ] | B AI4MARS images | `.../track-b-vehicles-ai4mars/` images + labels | 48 real frames, 12 synth | `_` |
| [x] | B trip timetable | `.../logistics_duty_cycle_100p_730sol.csv` | Simulated | `Storm vs clear terrain-risk means (0.50 → 0.73)` |
| [x] | B2 mobility grid | `.../track-b2-mobility-ai4mars/` | Fully synthetic | `Plain vs rock energy and stall; planned vs naive haul` |
| [x] | C ECLSS log | `.../track-c-life-support-hre/` | Simulated, not Mars500 telemetry | `Makeup water / O₂ and cabin CO₂, clear vs storm` |

### Open sandbox / local rasters

See [datasets.md](./datasets.md).

| Used | Dataset | Path | What we took from it |
| --- | --- | --- | --- |
| [x] | MOLA 4 / 16 ppd | `data/raw/mola/` | `Elevation and local slope; 4 ppd heightmap for the inspect mesh and custom-pin sample` |
| [x] | SWIM ice | `data/raw/swim/` | `Per-site ice consistency at 0–1 m, 1–5 m, and >5 m` |
| [ ] | Robbins craters | `data/raw/craters/` | `_` |
| [ ] | Curiosity REMS | `data/raw/weather/` | `_` |
| [x] | Curated sites | `data/raw/sites/candidate-sites.csv` | `NASA landing pins shown on the globe` |
| [x] | Other | `lib/mars-caves.ts` | `THEMIS Arsia Mons skylights (Cushing et al. 2007)` |

### Honest line for judges

One sentence. Example: "Weather and ECLSS tables are hack-ready simulations; the 48 rover frames are real AI4MARS, resized."

Radiation, seismic, wind-load and thermal depths are physics rules with cited constants, not site measurements. Weather, ECLSS, and the trip table are simulated. The B2 grid is synthetic. Storm-detector and terrain-cost scores recovered the generator.

Citations go in the README. Copy from [official-source/CREDITS.txt](./official-source/CREDITS.txt) for any official pack you ticked.

## 3. README and repo (must be in the pushed tree)

- [x] Track named in the README heading or first paragraph
- [x] 100-word summary of what we built
- [x] How ML was used (the one decision, the features, the output)
- [x] **Data used** section: every ticked row above, plus real vs simulated
- [x] How to run or view the demo (`pnpm`, `.venv`, which URL or script)
- [x] If this is a pre-existing startup idea, that is disclosed
- [x] No secrets, no `.env.local`
- [x] Public repo under the event org if they gave one, else the repo they asked for
- [x] Last commit timestamp before 20:35

## 4. Demo path (rehearse once)

Minute 0–1: the settlement problem (100 people, 730 sols, storm 180–260).

Minute 1–2: the thing on screen. Must be **stable**. No live training if you can avoid it.

Minute 2–3: the ML decision and why a first city would care.

Q&A: data honesty, feasibility, what you would do with another day.

- [x] Demo URL or command: `pnpm dev` then http://localhost:3000. Rehearsal is already on http://localhost:3005. Repo: https://github.com/ghcpuman902/mars-hackathon-2026
- [x] Backup screenshot or recording if the network dies: `docs/hackathon/demo/01-globe.png`, `docs/hackathon/demo/02-inspect.png`
- [x] Who speaks, who drives: solo, Mangle Kuo drives and talks

## 5. Do not overclaim

- [x] We did not call Track A or C "real EMARS / Mars500 telemetry"
- [x] We did not report synth-only image accuracy (B masks are identical)
- [x] We did not treat B2 as HiRISE/MOLA
- [x] Storm thermal swing: we did not "prove" dust-storm physics from Pack A
- [x] CO2 proxy in Pack C is mild (~1,200 ppm). We did not call it a cabin failure unless we added that ourselves

## 6. Freeze (20:25–20:35)

- [x] `LOCKS.md` or this file has track + data filled
- [x] README updated
- [x] Demo path works on a cold start
- [x] Commits staged and pushed
- [ ] Laptop on the demo URL, not the editor
