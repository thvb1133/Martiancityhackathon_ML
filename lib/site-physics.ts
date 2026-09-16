import { BEST_CAVE_ID, type MarsCave } from "@/lib/mars-caves"

/** MSL RAD surface GCR dose at Gale (−4.4 km). Hassler et al. 2014. */
export const RAD_SURFACE_DOSE_MSV_PER_DAY = 0.64
/** Cruise GCR dose. Zeitlin et al. 2013. */
export const RAD_CRUISE_DOSE_MSV_PER_DAY = 1.84
/** Atmospheric e-fold for dose (g/cm²), ~ln(cruise/2/surface) over Gale's column. */
export const ATMOS_ATTEN_G_CM2 = 45
export const GALE_COLUMN_G_CM2 = 22
export const GALE_ELEV_M = -4400
export const SCALE_HEIGHT_M = 11100
export const REGOLITH_DENSITY_G_CM3 = 1.5
/** Dose-equivalent e-fold in dry regolith. Röstel et al. 2020, order of magnitude. */
export const REGOLITH_ATTEN_G_CM2 = 70
export const DOSE_TARGET_MSV_PER_YEAR = 20
export const DOSE_TARGET_ALT_MSV_PER_YEAR = 50
export const SEP_SHELTER_DEPTH_M = 0.25

export const CERBERUS_FOSSAE = { lat: 10, lonEast: 160 }
export const INSIGHT_MAX_MW = 4.7
export const INSIGHT_EVENTS = 1300
const MARS_RADIUS_KM = 3389.5

/** Track A hourly series at Jezero (simulated). Hardcoded tonight. */
export const TRACK_A_WIND = {
  maxMs: 25.3,
  stormMedianMs: 14.2,
  clearMedianMs: 6.6,
}
export const TRACK_A_MEAN_TEMP_C = -56.2

export const SURFACE_PRESSURE_DATUM_PA = 610
export const R_CO2 = 188.9
export const T_MEAN_K = 217
export const EARTH_AIR_DENSITY_KG_M3 = 1.225

export const REGOLITH_DIFFUSIVITY_M2_S = 3e-7
export const MARS_YEAR_S = 5.94e7
export const SOL_S = 88775
export const HEAT_FLOW_W_M2 = 0.02
export const CONDUCTIVITY_W_MK = 2
export const GEOTHERMAL_PROBE_M = 5

export type SeismicTier = "elevated" | "moderate" | "low"

export type CaveVerdict = {
  nearest: MarsCave | null
  roofDepthM: number | null
  coversRadiation: boolean | null
  note: string
}

export type SitePhysics = {
  elevationM: number
  surfaceDoseMsvPerSol: number
  shieldingDepthM: number
  sepShelterDepthM: number
  cave: CaveVerdict
  seismic: { tier: SeismicTier; distanceKm: number }
  wind: {
    stormMedianPa: number
    peakPa: number
    earthPeakPa: number
    stormMedianMs: number
    peakMs: number
  }
  thermal: {
    diurnalSkinM: number
    annualSkinM: number
    meanTempC: number
    geothermalGain5mK: number
  }
}

export const atmosphericColumn = (elevM: number) => {
  return GALE_COLUMN_G_CM2 * Math.exp(-(elevM - GALE_ELEV_M) / SCALE_HEIGHT_M)
}

export const surfaceDose = (elevM: number) => {
  const column = atmosphericColumn(elevM)
  return RAD_SURFACE_DOSE_MSV_PER_DAY * Math.exp((GALE_COLUMN_G_CM2 - column) / ATMOS_ATTEN_G_CM2)
}

export const shieldingDepthM = (
  elevM: number,
  targetMsvYr = DOSE_TARGET_MSV_PER_YEAR,
) => {
  const annual = surfaceDose(elevM) * 365.25
  if (annual <= targetMsvYr) {
    return 0
  }
  const metres = (REGOLITH_ATTEN_G_CM2 / REGOLITH_DENSITY_G_CM3 / 100) * Math.log(annual / targetMsvYr)
  return Math.max(0, metres)
}

export const sepShelterDepthM = () => SEP_SHELTER_DEPTH_M

export const haversineKm = (
  lat1: number,
  lonEast1: number,
  lat2: number,
  lonEast2: number,
) => {
  const toRad = (deg: number) => (deg * Math.PI) / 180
  const dLat = toRad(lat2 - lat1)
  const dLon = toRad(((lonEast2 - lonEast1 + 540) % 360) - 180)
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2
  return 2 * MARS_RADIUS_KM * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export const seismicTier = (lat: number, lonEast: number) => {
  const distanceKm = haversineKm(
    lat,
    lonEast,
    CERBERUS_FOSSAE.lat,
    CERBERUS_FOSSAE.lonEast,
  )
  let tier: SeismicTier = "low"
  if (distanceKm < 500) {
    tier = "elevated"
  } else if (distanceKm < 1500) {
    tier = "moderate"
  }
  return { tier, distanceKm }
}

export const airDensity = (elevM: number) => {
  const pressure = SURFACE_PRESSURE_DATUM_PA * Math.exp(-elevM / SCALE_HEIGHT_M)
  return pressure / (R_CO2 * T_MEAN_K)
}

export const windPressurePa = (elevM: number, speedMs: number) => {
  return 0.5 * airDensity(elevM) * speedMs * speedMs
}

export const earthWindPressurePa = (speedMs: number) => {
  return 0.5 * EARTH_AIR_DENSITY_KG_M3 * speedMs * speedMs
}

export const skinDepthM = (periodS: number) => {
  return Math.sqrt((REGOLITH_DIFFUSIVITY_M2_S * periodS) / Math.PI)
}

export const geothermalGainK = (depthM: number) => {
  return (HEAT_FLOW_W_M2 / CONDUCTIVITY_W_MK) * depthM
}

export const caveVerdict = (
  caves: MarsCave[],
  _lat: number,
  _lonEast: number,
  coverM: number,
): CaveVerdict => {
  if (caves.length === 0) {
    return {
      nearest: null,
      roofDepthM: null,
      coversRadiation: null,
      note: "No published THEMIS cave pits in this ellipse. Arsia Mons is the cluster with named skylights.",
    }
  }

  const namedBest = caves.find((cave) => cave.id === BEST_CAVE_ID)
  const deepest = caves.reduce((winner, cave) => {
    const depth = cave.min_depth_m ?? -1
    const bestDepth = winner.min_depth_m ?? -1
    return depth > bestDepth ? cave : winner
  }, caves[0])
  const nearest = namedBest ?? deepest

  if (nearest.min_depth_m == null) {
    return {
      nearest,
      roofDepthM: null,
      coversRadiation: null,
      note: `${nearest.name} is a published pit; the floor stays in shadow, so roof thickness is unknown.`,
    }
  }

  const coversRadiation = nearest.min_depth_m >= coverM
  return {
    nearest,
    roofDepthM: nearest.min_depth_m,
    coversRadiation,
    note: coversRadiation
      ? `${nearest.name} roof ≥${nearest.min_depth_m} m, well above the ${coverM.toFixed(1)} m radiation cover.`
      : `${nearest.name} roof ≥${nearest.min_depth_m} m, still short of the ${coverM.toFixed(1)} m radiation cover.`,
  }
}

export const evaluateSite = (
  elevM: number,
  lat: number,
  lonEast: number,
  caves: MarsCave[],
): SitePhysics => {
  const coverM = shieldingDepthM(elevM)
  return {
    elevationM: elevM,
    surfaceDoseMsvPerSol: surfaceDose(elevM),
    shieldingDepthM: coverM,
    sepShelterDepthM: sepShelterDepthM(),
    cave: caveVerdict(caves, lat, lonEast, coverM),
    seismic: seismicTier(lat, lonEast),
    wind: {
      stormMedianPa: windPressurePa(elevM, TRACK_A_WIND.stormMedianMs),
      peakPa: windPressurePa(elevM, TRACK_A_WIND.maxMs),
      earthPeakPa: earthWindPressurePa(TRACK_A_WIND.maxMs),
      stormMedianMs: TRACK_A_WIND.stormMedianMs,
      peakMs: TRACK_A_WIND.maxMs,
    },
    thermal: {
      diurnalSkinM: skinDepthM(SOL_S),
      annualSkinM: skinDepthM(MARS_YEAR_S),
      meanTempC: TRACK_A_MEAN_TEMP_C,
      geothermalGain5mK: geothermalGainK(GEOTHERMAL_PROBE_M),
    },
  }
}
