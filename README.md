# MARSWATER

**Where should the first Martian city be built, and how big can it get before it breaks?**

Mars City Hackathon · GirlsWhoML × PhysicsX · Track: **Life Support & Resource Systems**

---

## What this is

One machine-learning model predicts how much water is buried under a candidate
landing site. Everything downstream of that prediction is deterministic
physics: sunlight, extraction energy, closed-loop life support, propellant
production, and the number of tonnes that have to be flown from Earth.

The tool answers three questions in order:

1. **Where is the water?** A gradient-boosted regressor predicts
   water-equivalent hydrogen from orbital observables — latitude, elevation,
   thermal inertia, albedo, dust cover, radar dielectric contrast and mapped
   geology.
2. **What does each site cost to settle?** For a target crew size, the
   simulation sizes the solar array, energy storage, reactors, excavator fleet
   and extraction plant that site would need, and ranks candidates by landed
   mass.
3. **Where does it break?** Raising the population shrinks the viable
   shortlist until nothing qualifies — and the tool says which piece of
   hardware would reopen it.

## The result

Running the pipeline on 24 real candidate sites, with propellant production
enabled and four 10 kWe reactors:

| Crew size | Viable sites (of 24) | Best site | Landed mass |
|---|---|---|---|
| 20 | 24 | Erebus Montes | 66 t |
| 100 | 12 | Erebus Montes | 180 t |
| 1,000 | 10 | Erebus Montes | 1,799 t |
| 2,000 | 6 | Erebus Montes | 3,599 t |
| 4,000 | **0** | — | — |

Three findings came out of the simulation rather than being designed into it.

**The propellant plant decides where you land, not the crew.** A closed ECLSS
recycles about 93% of the water the crew uses, so 100 people need only
180 kg of makeup water per sol. Fuelling one departing vehicle consumes
roughly 600 t of mined water, which is about 900 kg per sol averaged over a
launch window. Committing to a return capability multiplies water demand
tenfold and eliminates **half the shortlist immediately** — sites that are
perfectly good one-way outposts cannot support a spaceport.

**Ore grade is a power problem, not just a water problem.** Recovering a
kilogram of water means heating `100/grade` kilograms of regolith. At 23 wt%
that is 4 kg of rock; at 0.5 wt% it is 200 kg. Dry equatorial sites do not
merely cost more — they demand 27 excavators where the maintainable fleet limit
is 24, so they fail outright.

**At 4,000 people, more power does not help.** The binding constraint has
switched from the power budget to rock throughput, so the fix is a richer
deposit or a bigger mining fleet, not more reactors. The tool detects this and
says so instead of reporting a dead end.

## Running it

```bash
pip install -r requirements.txt

# Headless demo: full argument printed in about 8 seconds
python -m marswater.cli

# Interactive dashboard with the map and the population slider
streamlit run app.py

# Tests
pytest -q
```

The CLI takes `--population`, `--fission-units`, `--top` and `--seed`.

## How the machine learning is used

**One model, one decision.** A `GradientBoostingRegressor` predicts
water-equivalent hydrogen in weight percent from ten orbital observables. It is
the only learned component in the project; keeping it to one prediction means a
judge can check the rest of the pipeline by hand, and the model's error bars
propagate into the siting decision instead of being hidden between layers of
models.

**Validation.** Trained on 3,150 survey cells, scored on 1,050 held out:

| Model | Held-out R² |
|---|---|
| Gradient boosting | **0.935** |
| Ridge regression | 0.889 |
| Mean baseline | −0.001 |

Five-fold cross-validated R² is 0.932 ± 0.006, and mean absolute error is
2.3 wt% water. The gap over ridge regression is the point of using a tree
ensemble: ground ice is only preserved where it is *both* thermodynamically
stable *and* geologically emplaced, and that thresholded interaction is not
linearly representable. Permutation importance puts absolute latitude first,
radar dielectric contrast second and the mapped geologic unit third, which is
the ordering the ground-ice literature would predict.

**The prediction is used pessimistically.** Sizing a water plant on the mean
forecast fails half the time the forecast is wrong, which is not an acceptable
risk posture for the crew's only source of drinking water and breathing oxygen.
Every downstream calculation uses the prediction minus one residual sigma.

**Proof that the model is load bearing.** Hold every assumption fixed and
change only whether the settlement produces return propellant. The recommended
site's water demand goes from 0.18 to 1.98 t/sol, required landed mass goes
from 83 t to 180 t, and the viable shortlist halves from 24 sites to 12. If the
water prediction were decorative, none of that would move.

## The physics

Every constant is sourced in [`marswater/constants.py`](marswater/constants.py).

- **Insolation** — sol-integrated beam radiation from Mars' real orbital
  geometry (e = 0.0934, obliquity 25.19°, perihelion at Ls 251°), attenuated by
  Beer-Lambert extinction through the dust column with a forward-scattered
  diffuse recovery term, and thinned with elevation on an 11.1 km dust scale
  height.
- **Extraction energy** — regolith specific heat and ΔT to release adsorbed
  ice, water's enthalpy of sublimation, excavation work, heat recovery and
  plant efficiency, all scaled by the model's predicted ore grade.
- **Life support** — crew consumption rates from the NASA Baseline Values and
  Assumptions Document, with ECLSS loop closure and 9/8 electrolysis
  stoichiometry for oxygen.
- **Propellant** — Sabatier (CO₂ + 4H₂ → CH₄ + 2H₂O) with hydrogen from
  electrolysed ground water; about 1,175 t electrolysed per ~1,200 t methalox
  load, roughly half returned by the reaction, so about 600 t net mined water
  per departure.
- **Hardware** — triple-junction cell efficiency, packing factor, dust-settling
  derate, battery round-trip efficiency and pack specific energy,
  Kilopower-class 10 kWe reactor units, and an extraction plant whose mass
  scales with rock throughput.

Hard constraints: 15° slope limit for entry, descent and landing; 22% rock
abundance limit for array and habitat layout; a 24-unit excavator fleet
maintenance limit; and a 1.5 km² solar farm footprint limit.

## Data provenance

This matters, so it is stated plainly rather than buried.

**Real:** the 24 named candidate sites use their actual published coordinates
and MOLA elevations, drawn from NASA human-landing-site studies and robotic
mission site selections (Arcadia Planitia, Deuteronilus Mensae, Jezero,
Gale, Hellas, and others). Every physical constant is a published figure with
its source noted in the code.

**Surrogate:** the orbital survey the model trains on is generated, not
measured. The real products — Mars Odyssey Neutron Spectrometer
water-equivalent hydrogen maps, TES thermal inertia, MOLA topography, SHARAD
radar soundings — are multi-gigabyte Planetary Data System archives that cannot
be downloaded and georeferenced inside a two-hour hackathon window. The
generator encodes four published results about Martian ground ice:

1. Shallow ice is thermodynamically stable poleward of roughly ±50° latitude
   (Mellon & Jakosky 1993).
2. A relict mid-latitude band near 30–50° holds debris-covered glacial ice from
   a higher-obliquity epoch.
3. High thermal inertia indicates ice-cemented rather than loose regolith.
4. Dark, low-albedo ground runs warmer and loses shallow ice faster.

The model never sees that generator — only noisy observables and noisy labels,
with measurement noise that grows with water content the way neutron
spectrometer counting statistics do. It has to recover the relationship, and
the reported R² is genuinely out-of-sample. **This is a stand-in for the PDS
archive and is not presented as measured data.** Swapping in the real rasters
means replacing one function, `dataset.labelled_survey`; the feature schema and
everything downstream are unchanged.

## Layout

```
marswater/
  constants.py   sourced physical and hardware constants
  physics.py     insolation, extraction energy, life support and propellant demand
  sites.py       real candidate sites; synthetic areoid for the survey grid
  dataset.py     observable generation and the labelled surrogate survey
  model.py       the one learned component, with baselines and uncertainty
  simulate.py    infrastructure sizing, ranking, breakpoints, storm scenarios
  pipeline.py    train, then score every candidate site
  cli.py         headless end-to-end demo
app.py           Streamlit dashboard
tests/           102 tests covering physics, model, simulation and dashboard
```

## Honest limitations

- The training survey is a surrogate (see above). The reported R² measures
  whether the model can recover a physically motivated field from noisy
  observables — not whether it can predict real Martian ice.
- Insolation is computed for a horizontal surface at a single solar longitude.
  Tracking arrays, tilt optimisation and full seasonal integration are not
  modelled.
- Extraction is modelled as a bulk-heating energy and throughput budget. No
  geotechnical model of overburden depth, drilling or spoil handling.
- The excavator fleet limit and the extraction plant's mass-per-throughput are
  engineering judgements, not sourced figures. Both are exposed as parameters
  because both materially affect where the breakpoint falls.
- Radiation shielding, habitat structures and crew health are out of scope.

## Scaling from prototype to deployment

The feature schema is already the schema of the real orbital products, so the
path forward is concrete: georeference the Odyssey neutron spectrometer WEH map
with TES thermal inertia and MOLA topography onto a shared grid, retrain the
same estimator on measured labels, and the ranking, breakpoint and hardware
prescription all work unchanged. The physics layer needs no modification at
all — it is already sized in real units against published constants.
