# Demo runbook

Three minutes of build, two minutes of Q&A. This is the script, the failure
plan, and the answers to the questions the rubric invites.

---

## Before you present

```bash
streamlit run app.py
```

Open the page once and leave it open. The model trains on first load and is
cached afterwards, so a cold start costs several seconds and every slider move
after that is instant. You do not want the training run happening during your
three minutes.

Have a second terminal ready with `python -m marswater.cli` typed but not run.
That is the fallback: it prints the entire argument in about eight seconds with
no browser, no projector resolution problem and no venue WiFi.

Set the sidebar to: **population 100, fission units 4, dust clear, propellant
production ON**.

---

## The three minutes

**0:00 — The decision, not the technology.** "Everything a Martian city needs
is downstream of one choice: where you land. Get it wrong and you spend the
next century trucking water. We built the tool that makes that choice, and the
thing it told us is not what we expected."

**0:25 — The globe.** Rotate it. "This is our model's prediction of subsurface
water across Mars, draped on real topography. The pale bands either side of the
equator are mid-latitude mantling deposits — buried glacial ice. The model was
never told they exist. It found them from latitude, thermal inertia, radar
contrast and mapped geology, and it scores 0.935 R² on ground it never trained
on, against 0.889 for a linear baseline."

**1:00 — The counter-intuitive finding.** Untick **Produce return propellant
from ice**, then tick it again. "Watch the shortlist. A one-way outpost recycles
93% of its water, so 100 people need 180 kg a sol — nothing. The moment you
commit to sending anyone home, you are electrolysing 600 tonnes of mined water
per departing vehicle. Water demand goes up tenfold and **half our 24 candidate
sites stop qualifying.** The propellant plant decides where you land, not the
crew. That is not a result we designed in; it fell out of the numbers."

**1:45 — The 3D base.** Scroll to the settlement plan. "This is not a concept
drawing. The solar farm is the computed array area in square metres. The dome
count is 60 cubic metres of pressurised volume per person. The mine is one
launch window of excavation." Drag population to **1000**. "Two domes become
seventeen, the farm goes from 218 metres square to 702." Then the key line:
"And if I hold the crew at 100 and only make the ground drier — 25% water down
to 2% — the pit grows from 21 metres to 48, because forty times more rock has
to be heated for the same litres. That pit **is** the machine learning output."

**2:30 — Where it breaks.** Drag population to **4000**. "Nothing works. And
the useful part is the diagnosis: it tells us more reactors will not help,
because the binding constraint has switched from power to rock throughput. We
need a richer deposit or a bigger mining fleet. A tool that only ranks sites
cannot tell you that."

**2:50 — Close.** "One model, one decision, and a physics layer you can check
by hand. 145 tests. Recommendation: land at Erebus Montes."

---

## Prepared answers

**"Is this real Mars data?"** Partly, and we are precise about which parts. The
24 sites are real — published coordinates and MOLA elevations from NASA landing
site studies. Every physical constant is sourced in `constants.py`. The training
survey is a surrogate, because the real products are multi-gigabyte PDS
archives we could not georeference in two hours. It encodes four published
ground-ice results, the model never sees the generator, so the R² is genuinely
out-of-sample. And the swap is code, not a promise: `marswater/realdata.py`
samples real georeferenced rasters through rasterio, and there is a test that
loads a survey from disk and trains the model on it.

**"Why does water beat sunlight? Sunlight is the obvious constraint."** It
does not, until you include propellant — and that is the mistake our first
version made. Ranking on crew water and solar supply alone gave a ranking
driven purely by latitude, because habitat overhead swamped the water term and
the prediction barely changed the answer. Adding methalox production is what
made water decisive, and it is also the real reason Mars architectures are
sited on ice.

**"Why gradient boosting and not a neural network, or just a regression?"**
Ground ice survives only where it is *both* thermodynamically stable *and*
geologically emplaced. That is a thresholded interaction, which a linear model
cannot represent — that is the 0.889 to 0.935 gap, and we report the ridge
baseline precisely so the choice is justified rather than assumed. A neural
network on 4,200 tabular rows would be a worse tool and a longer training run.

**"How do you know the model is doing any work at all?"** Toggle the propellant
switch. Same model, same physics, one assumption changed: the recommended
site's water demand moves from 0.18 to 1.98 t/sol, landed mass from 83 to 180
tonnes, viable sites from 24 to 12. If the prediction were decorative, none of
that would move.

**"What happens in a dust storm?"** It is in the tool, because a solar
settlement plan that does not state this is incomplete. At Erebus Montes a
global storm at optical depth 4.5 cuts specific yield from 0.541 to 0.412
kWh/m²/sol and the population ceiling from 3,047 to 2,300. The reactors are
what carry you through, which is why they are sized first and the array makes
up the remainder.

**"What would you do with another day?"** Georeference the real Odyssey
neutron spectrometer map and retrain — the adapter is written and tested, so
that is a data task, not an engineering one. Then relax the two assumptions we
are least confident in: the excavator fleet limit and the extraction plant's
mass per unit throughput. Both are engineering judgements rather than sourced
figures, both are exposed as parameters, and both move where the breakpoint
falls. They are listed as limitations in the README for exactly that reason.

**"Could this actually scale to a real settlement?"** The physics layer needs
no modification — it is already in real units against published constants, and
it already reports answers in tonnes landed and Starship loads. The feature
schema is the schema of the real orbital products. What is missing is measured
data and a geotechnical model of overburden and drilling, not a rewrite.

---

## If something goes wrong

| Problem | Do this |
|---|---|
| Browser or projector fails | `python -m marswater.cli` — full argument, ~8 s, text only |
| App is slow or stuck | Reload once; the model is cached after first load |
| 3D looks wrong on the projector | Switch to the **Flat map** tab; same data, 2D |
| An `AttributeError` appears after you edit code | A stale server is serving old modules — see below |
| Asked for code mid-demo | `marswater/physics.py` for the physics, `model.py` for the one model |

### Restarting cleanly

Streamlit reruns `app.py` on save but does not always reload changed classes in
imported modules, so editing a dataclass and refreshing can leave you looking
at an error that no longer exists in the code. Worse, `Ctrl-C` on a piped
`streamlit run ... | tail` kills the pipe rather than the server, and the next
`streamlit run` then fails silently on the busy port while the old process
keeps serving. Verify the restart actually happened:

```bash
pkill -f "streamlit run"; sleep 3
pgrep -f "streamlit run" || echo "stopped"     # must print: stopped
streamlit run app.py
```

If an error persists after a genuine restart, it is real. Confirm with
`pytest -q tests/test_app.py`, which executes the dashboard in-process against
the code on disk and cannot be fooled by a stale server.
