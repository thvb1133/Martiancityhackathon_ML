export type LandingSite = {
  id: string
  name: string
  lat_deg: number
  lon_east_deg: number
  archetype: string
  why_it_matters: string
  tracks: string
  elevation_m: number | null
  slope_deg_local: number | null
  ice_0_1m: number | null
  ice_1_5m: number | null
  ice_gt_5m: number | null
}

export type LandingPick = {
  lat_deg: number
  lon_east_deg: number
  siteId?: string
}

export type CustomSite = {
  id: string
  lat_deg: number
  lon_east_deg: number
}

export const isCustomSiteId = (siteId?: string) => {
  return Boolean(siteId?.startsWith("custom-") || siteId === "custom")
}

export const customSiteHref = (lat_deg: number, lon_east_deg: number) => {
  const lat = lat_deg.toFixed(4)
  const lon = lon_east_deg.toFixed(4)
  return `/site/custom?lat=${lat}&lon=${lon}`
}

export const siteHref = (siteId: string, lat_deg?: number, lon_east_deg?: number) => {
  if (isCustomSiteId(siteId) && lat_deg != null && lon_east_deg != null) {
    return customSiteHref(lat_deg, lon_east_deg)
  }
  return `/site/${siteId}`
}

export const makeCustomSite = (lat_deg: number, lon_east_deg: number): CustomSite => {
  return {
    id: `custom-${Date.now()}`,
    lat_deg,
    lon_east_deg,
  }
}

export const JEZERO: LandingPick = {
  lat_deg: 18.38,
  lon_east_deg: 77.58,
  siteId: "jezero",
}

export const formatLatLon = (lat: number, lonEast: number) => {
  const latHem = lat >= 0 ? "N" : "S"
  const lon = ((lonEast % 360) + 360) % 360
  return `${Math.abs(lat).toFixed(2)}°${latHem}  ${lon.toFixed(2)}°E`
}

export const uvToLatLon = (u: number, v: number): LandingPick => {
  const lon_east_deg = ((u % 1) + 1) % 1 * 360
  const lat_deg = v * 180 - 90
  return { lat_deg, lon_east_deg }
}

export const lonEastTo180 = (lonEast: number) => {
  const east = ((lonEast % 360) + 360) % 360
  return east > 180 ? east - 360 : east
}

export const vikingTileUrl = (lat: number, lonEast: number, level = 6) => {
  const lon180 = lonEastTo180(lonEast)
  const tilesX = 2 * 2 ** level
  const tilesY = 2 ** level
  const x = Math.min(
    tilesX - 1,
    Math.max(0, Math.floor(((lon180 + 180) / 360) * tilesX)),
  )
  const y = Math.min(
    tilesY - 1,
    Math.max(0, Math.floor(((90 - lat) / 180) * tilesY)),
  )
  return `https://trek.nasa.gov/tiles/Mars/EQ/Mars_Viking_MDIM21_ClrMosaic_global_232m/1.0.0/default/default028mm/${level}/${y}/${x}.jpg`
}

export const lon180ToEast = (lon180: number) => {
  return ((lon180 % 360) + 360) % 360
}

export const latLonToUv = (lat: number, lonEast: number) => {
  const lon = ((lonEast % 360) + 360) % 360
  return { u: lon / 360, v: (lat + 90) / 180 }
}

export const shortSiteName = (name: string) => {
  return name
    .replace(" crater", "")
    .replace(" Planitia", "")
    .replace(" lava tubes", "")
    .replace(" caves", "")
}

export const nearestSite = (
  sites: LandingSite[],
  lat: number,
  lonEast: number,
  maxDeg = 3,
) => {
  let best: LandingSite | undefined
  let bestDist = maxDeg
  for (const site of sites) {
    const dlat = site.lat_deg - lat
    const dlon = ((site.lon_east_deg - lonEast + 540) % 360) - 180
    const dist = Math.hypot(dlat, dlon)
    if (dist < bestDist) {
      best = site
      bestDist = dist
    }
  }
  return best
}
