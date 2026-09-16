import type { LandingSite } from "@/lib/mars-landing"
import {
  SETTLEMENT,
  iceBand,
  isPackWeatherSite,
  type IceBand,
} from "@/lib/settlement"
import { siteCopy } from "@/lib/site-copy"
import type { SitePhysics } from "@/lib/site-physics"

export type AnalysisRow = {
  label: string
  value: string
}

export type SiteAnalysis = {
  verdict: string
  facts: string
  lead: string | null
  rows: AnalysisRow[]
  storm: string
  water: string
  dig: string
  showSparkline: boolean
}

const SITE_LEAD: Record<string, string> = {
  jezero: "Perseverance ground, and the weather series.",
  gale: "Curiosity. RAD was calibrated here.",
  oxia: "Rosalind Franklin ellipse. Clay, no ice.",
  mawrth: "Clay shortlist. Contrast to the ice belt.",
  arcadia: "SWIM ice belt. Water over solar.",
  deuteronilus: "Debris-covered ice.",
  phlegra: "Ice plus relief.",
  utopia: "Northern basin ice. Flat.",
  hellas: "Deepest basin. Highest pressure.",
  isidis: "Next to Jezero. Logistics hub case.",
  elysium: "InSight plains. Flat, no ice.",
  acidalia: "Northern lowlands.",
  valles: "Canyon shelter. Hard EDL.",
  meridiani: "Opportunity. Flat hematite.",
  chryse: "Viking 1. Low outflow mouth.",
  arsia: "THEMIS skylights. You came for the roof.",
  pavonis: "Tube-fed flank. Published pits sit on Arsia.",
  olympus: "Twenty kilometres up. Landmark, not a first city.",
  annie: "Best published pit on this map.",
  dena: "THEMIS pit on Arsia.",
  wendy: "THEMIS pit on Arsia.",
  jeanne: "THEMIS pit on Arsia.",
}

const metres = (value: number) => {
  const rounded = Math.round(value * 10) / 10
  if (Number.isInteger(rounded)) {
    return `${rounded}`
  }
  return rounded.toFixed(1)
}

const elevLabel = (elevM: number) => {
  const rounded = Math.round(elevM)
  const abs = Math.abs(rounded).toLocaleString("en-US")
  return rounded < 0 ? `−${abs} m` : `${abs} m`
}

const score = (value: number) => {
  const rounded = value.toFixed(2)
  if (value > 0) {
    return `+${rounded}`
  }
  if (value < 0) {
    return rounded.replace("-", "−")
  }
  return "0"
}

const iceLabel = (site: LandingSite | undefined, band: IceBand) => {
  if (band === "unknown") {
    return "ice off SWIM"
  }
  if (!site) {
    return "no ice score"
  }
  const parts = [site.ice_0_1m, site.ice_1_5m, site.ice_gt_5m]
    .filter((value): value is number => value != null)
    .map(score)
  if (parts.length === 0) {
    return "no ice score"
  }
  return `ice ${parts.join(" / ")}`
}

const slopeLabel = (site?: LandingSite) => {
  if (site?.slope_deg_local == null) {
    return null
  }
  return `${site.slope_deg_local.toFixed(1)}°`
}

export const analyseSite = (
  report: SitePhysics,
  lat: number,
  lonEast: number,
  site?: LandingSite
): SiteAnalysis => {
  const copy = siteCopy(report, site)
  const band = iceBand(site)
  const onWeatherPin = isPackWeatherSite(lat, lonEast)
  const slope = slopeLabel(site)
  const facts = [elevLabel(report.elevationM), slope, iceLabel(site, band)]
    .filter((part): part is string => Boolean(part))
    .join(" · ")

  const rows: AnalysisRow[] = []
  if (report.cave.coversRadiation && report.cave.roofDepthM != null) {
    rows.push({
      label: "roof",
      value: `≥${metres(report.cave.roofDepthM)} m`,
    })
  }
  rows.push({
    label: "dose",
    value: `${report.surfaceDoseMsvPerSol.toFixed(2)} mSv/sol`,
  })
  rows.push({
    label: "quake",
    value: `${report.seismic.tier} · ${Math.round(report.seismic.distanceKm).toLocaleString("en-US")} km`,
  })
  rows.push({
    label: "wind",
    value: `${report.wind.peakPa.toFixed(1)} Pa · doors SW`,
  })
  rows.push({
    label: "skin",
    value: `${metres(report.thermal.annualSkinM)} m`,
  })

  const { heating, solar, ml, terrain, eclss, dust } = SETTLEMENT
  const plain = terrain.regolith_plain
  const rock = terrain.rock_field
  const slopeDeg = site?.slope_deg_local ?? 0

  const heatClear = Math.round(heating.clearMean)
  const heatStorm = Math.round(heating.stormMean)
  const tauOnset = Number(dust.sol179).toFixed(2)
  const tauStorm = Number(dust.sol180).toFixed(1)
  const storm = onWeatherPin
    ? `Detector trips sol ${ml.stormDetector.tripSol} from wind and temperature, not dust. τ ${tauOnset} → ${tauStorm}. Heat ${heatClear} → ${heatStorm} kW. Solar ${solar.clearMean} → ${solar.stormMean} kWh/m².`
    : `Storm numbers are Jezero-band, a warm bound. Detector still trips sol ${ml.stormDetector.tripSol}. Heat ${heatClear} → ${heatStorm} kW there.`

  const lead = report.cave.coversRadiation
    ? null
    : (SITE_LEAD[site?.id ?? ""] ?? null)

  let water = `${eclss.makeupPlusElectrolysisKgDay} kg/day makeup for 100 people.`
  if (band === "shallow") {
    water = `Ice in the first metre. ${water} That is why you leave 18°N.`
  } else if (band === "buried") {
    water = `Ice below a metre. ${water}`
  } else if (band === "unknown") {
    water = `SWIM does not score this latitude. Polar ice is certain; winter solar is not.`
  } else if (onWeatherPin) {
    water = `No shallow ice. ${water} It has to be trucked or shipped.`
  } else {
    water = `No shallow ice here. ${water}`
  }

  let dig = `Plain ${plain.energyWhPerM} Wh/m vs rock ${rock.energyWhPerM}. Planned haul ${ml.terrain.plannedWh.toLocaleString("en-US")} Wh; pack ${ml.terrain.swarmPackWh.toLocaleString("en-US")} Wh.`
  if (report.cave.coversRadiation) {
    dig = `${report.cave.nearest?.name ?? "This pit"} is the cover. Do not pile dirt on the roof.`
  } else if (slopeDeg >= 8) {
    dig = `Slope ${slopeDeg.toFixed(1)}°. The B2 cost surface is a flat 20 m grid. This pin is not a trench site.`
  } else if (report.elevationM > 5000) {
    dig = `High ground. Cover is the limiter. ${dig}`
  }

  return {
    verdict: copy.headline,
    facts,
    lead,
    rows,
    storm,
    water,
    dig,
    showSparkline: onWeatherPin,
  }
}
