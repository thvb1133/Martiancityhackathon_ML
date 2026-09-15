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

export const CAVES_CREDIT =
  "Cushing et al. 2007, THEMIS skylights on Arsia Mons. Diameters 100–252 m. Floors stay in shadow, so depth is a minimum."

export const cavesNear = (
  lat: number,
  lonEast: number,
  maxDeg = 4,
) => {
  return MARS_CAVES.filter((cave) => {
    const dlat = cave.lat_deg - lat
    const dlon = ((cave.lon_east_deg - lonEast + 540) % 360) - 180
    return Math.hypot(dlat, dlon) <= maxDeg
  })
}
