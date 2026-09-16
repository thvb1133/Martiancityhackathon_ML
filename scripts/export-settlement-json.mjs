/**
 * Pack a compact settlement payload for the Next.js app from the Sol Zero
 * Console series (public/sol-zero-console/marsdata.js).
 *
 * That file is the already-exported daily series from the official packs.
 * This script does not retrain models; it summarises the series the console
 * already ships and attaches the published CV scores from ml/settlement.
 *
 * Run: node scripts/export-settlement-json.mjs
 */
import { readFileSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const root = join(dirname(fileURLToPath(import.meta.url)), "..")
const source = readFileSync(
  join(root, "public/sol-zero-console/marsdata.js"),
  "utf8",
)
const jsonText = source.slice(source.indexOf("{"), source.lastIndexOf("}") + 1)
const data = JSON.parse(jsonText)

const STORM_START = 180
const STORM_END = 260
const STEP = 5
const TERRAIN = [
  "regolith_plain",
  "rock_field",
  "crater_floor",
  "crater_rim",
  "dune_field",
  "dust_pit",
  "lava_tube_entrance",
]

const mean = (values) => values.reduce((sum, value) => sum + value, 0) / values.length
const bySol = (values, predicate) =>
  values.filter((_, sol) => predicate(sol))

const isStorm = (sol) => sol >= STORM_START && sol <= STORM_END
const clearSolar = bySol(data.solkwh, (sol) => !isStorm(sol))
const stormSolar = bySol(data.solkwh, isStorm)
const clearLoad = bySol(data.load, (sol) => !isStorm(sol))
const stormLoad = bySol(data.load, isStorm)
const clearTau = bySol(data.tau, (sol) => !isStorm(sol))
const stormTau = bySol(data.tau, isStorm)
const clearTmin = bySol(data.tmin, (sol) => !isStorm(sol))
const stormTmin = bySol(data.tmin, isStorm)
const clearRisk = bySol(data.risk, (sol) => !isStorm(sol))
const stormRisk = bySol(data.risk, isStorm)

const downsample = (values) => {
  const next = []
  for (let sol = 0; sol < values.length; sol += STEP) {
    next.push(values[sol])
  }
  return next
}

const terrain = {}
for (const [index, name] of TERRAIN.entries()) {
  const energy = []
  const hazard = []
  for (let i = 0; i < data.grid_t.length; i += 1) {
    if (data.grid_t[i] === index) {
      energy.push(data.grid_e[i])
      hazard.push(data.grid_h[i])
    }
  }
  if (energy.length === 0) {
    continue
  }
  terrain[name] = {
    cells: energy.length,
    energyWhPerM: Number(mean(energy).toFixed(2)),
    hazard: Number(mean(hazard).toFixed(2)),
  }
}

const roseStrong = data.rose_strong
const roseStrongTotal = roseStrong.reduce((sum, value) => sum + value, 0)

const payload = {
  source: {
    weather:
      "Track A EMARS-informed hourly series at 18.4°N 77.5°E (Jezero band). Simulated.",
    terrain: "Track B2 synthetic 60×60 grid and 1,500 labelled routes.",
    eclss: "Track C simulated daily ECLSS table, not Mars500 telemetry.",
  },
  site: { lat: 18.4, lon: 77.5, name: "Jezero band" },
  storm: { startSol: STORM_START, endSol: STORM_END, sols: STORM_END - STORM_START + 1 },
  solar: {
    clearMean: Number(mean(clearSolar).toFixed(2)),
    stormMean: Number(mean(stormSolar).toFixed(2)),
    stormMin: Number(Math.min(...stormSolar).toFixed(2)),
  },
  heating: {
    clearMean: Number(mean(clearLoad).toFixed(1)),
    stormMean: Number(mean(stormLoad).toFixed(1)),
    peak: Number(Math.max(...data.load).toFixed(1)),
  },
  temperature: {
    mean: Number(mean(data.tmin.map((lo, i) => (lo + data.tmax[i]) / 2)).toFixed(1)),
    min: Math.min(...data.tmin),
    max: Math.max(...data.tmax),
    clearMeanMin: Number(mean(clearTmin).toFixed(1)),
    stormMeanMin: Number(mean(stormTmin).toFixed(1)),
  },
  dust: {
    clearMean: Number(mean(clearTau).toFixed(2)),
    stormMean: Number(mean(stormTau).toFixed(2)),
    sol179: data.tau[179],
    sol180: data.tau[180],
  },
  wind: {
    roseAll: data.rose_all,
    roseStrong,
    shareStrongTowardNE: Number((roseStrong[1] / roseStrongTotal).toFixed(3)),
    sectors: ["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
  },
  risk: {
    clearMean: Number(mean(clearRisk).toFixed(3)),
    stormMean: Number(mean(stormRisk).toFixed(3)),
  },
  eclss: {
    waterMakeupMeanKg: Number(mean(data.wmake).toFixed(1)),
    o2MakeupMeanKg: Number(mean(data.o2make).toFixed(1)),
    co2ClearPpm: Number(mean(bySol(data.co2, (sol) => !isStorm(sol))).toFixed(0)),
    co2StormPpm: Number(mean(bySol(data.co2, isStorm)).toFixed(0)),
    waterUseKgDay: 355,
    o2UseKgDay: 89,
    foodKgDay: 183,
    foodT730: 134,
    makeupPlusElectrolysisKgDay: 28,
  },
  terrain,
  ml: {
    stormDetector: {
      auc: 1.0,
      tripSol: 180,
      lagSols: 0,
      features: [
        "temperature_c",
        "ws",
        "surface_pressure_pa",
        "hour",
        "t_anom",
        "ws_roll6",
      ],
    },
    heating: { r2: 0.999 },
    terrain: {
      energyR2: 0.99,
      hazardR2: 0.98,
      routeAuc: 0.995,
      plannedWh: 2283,
      naiveWh: 2886,
      swarmPackWh: 1200,
    },
  },
  series: {
    step: STEP,
    sols: downsample(data.solkwh.map((_, sol) => sol)),
    tau: downsample(data.tau),
    solar: downsample(data.solkwh),
    load: downsample(data.load),
  },
}

const dest = join(root, "public/data/settlement.json")
writeFileSync(dest, `${JSON.stringify(payload, null, 2)}\n`)
console.log(`wrote ${dest} (${Math.round(JSON.stringify(payload).length / 1024)} KB)`)
