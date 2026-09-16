export type MarsCave = {
  id: string
  name: string
  lat_deg: number
  lon_east_deg: number
  diameter_m: number
  min_depth_m: number | null
  host: string
}

export const MARS_CAVES: MarsCave[] = [
  {
    id: "dena",
    name: "Dena",
    lat_deg: -6.31,
    lon_east_deg: 239.02,
    diameter_m: 162,
    min_depth_m: 80,
    host: "Arsia Mons",
  },
  {
    id: "chloe",
    name: "Chloë",
    lat_deg: -4.29,
    lon_east_deg: 239.21,
    diameter_m: 252,
    min_depth_m: null,
    host: "Arsia Mons",
  },
  {
    id: "wendy",
    name: "Wendy",
    lat_deg: -7.84,
    lon_east_deg: 240.32,
    diameter_m: 125,
    min_depth_m: 68,
    host: "Arsia Mons",
  },
  {
    id: "annie",
    name: "Annie",
    lat_deg: -6.52,
    lon_east_deg: 240.03,
    diameter_m: 225,
    min_depth_m: 101,
    host: "Arsia Mons",
  },
  {
    id: "abby",
    name: "Abby",
    lat_deg: -6.713,
    lon_east_deg: 240.54,
    diameter_m: 100,
    min_depth_m: null,
    host: "Arsia Mons",
  },
  {
    id: "nikki",
    name: "Nikki",
    lat_deg: -6.708,
    lon_east_deg: 240.55,
    diameter_m: 180,
    min_depth_m: null,
    host: "Arsia Mons",
  },
  {
    id: "jeanne",
    name: "Jeanne",
    lat_deg: -5.57,
    lon_east_deg: 241.38,
    diameter_m: 165,
    min_depth_m: 75,
    host: "Arsia Mons",
  },
]

export const BEST_CAVE_ID = "annie"

export const CAVES_CREDIT =
  "Cushing et al. 2007, THEMIS skylights on Arsia Mons. Diameters 100–252 m. Floors stay in shadow, so depth is a minimum."

export const caveEntityId = (caveId: string) => {
  return `cave-${caveId}`
}

export const caveIdFromEntity = (entityId: string) => {
  if (!entityId.startsWith("cave-")) {
    return undefined
  }
  return entityId.slice(5)
}

export const pinDistanceDeg = (
  latA: number,
  lonEastA: number,
  latB: number,
  lonEastB: number,
) => {
  const dlat = latA - latB
  const dlon = ((lonEastA - lonEastB + 540) % 360) - 180
  return Math.hypot(dlat, dlon)
}

export const caveDistanceDeg = (
  cave: MarsCave,
  lat: number,
  lonEast: number,
) => {
  return pinDistanceDeg(cave.lat_deg, cave.lon_east_deg, lat, lonEast)
}

export const caveFact = (cave: MarsCave) => {
  if (cave.min_depth_m == null) {
    return `${cave.host} skylight. Floor stays in shadow, so the roof is unknown. Measure before you skip the dirt pile.`
  }
  return `${cave.host} skylight. Roof ≥${cave.min_depth_m} m. That already beats the radiation pile. Live under the cave.`
}

export const cavesNear = (
  lat: number,
  lonEast: number,
  maxDeg = 4,
) => {
  return MARS_CAVES.filter((cave) => caveDistanceDeg(cave, lat, lonEast) <= maxDeg)
}

export const nearestCave = (
  lat: number,
  lonEast: number,
  maxDeg = 0.2,
) => {
  let best: MarsCave | undefined
  let bestDist = maxDeg
  for (const cave of MARS_CAVES) {
    const dist = caveDistanceDeg(cave, lat, lonEast)
    if (dist <= bestDist) {
      best = cave
      bestDist = dist
    }
  }
  return best
}
