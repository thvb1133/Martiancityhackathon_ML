import { sampleMolaBilinear, type MolaGrid } from "@/lib/mola-heightmap"
import { BEST_CAVE_ID, type MarsCave } from "@/lib/mars-caves"

export const TERRAIN_CELLS = 192
export const TERRAIN_SPAN_DEG = 2.2
export const CAVE_FRAME_DEG = 1.25

export const cavesInFrame = (
  caves: MarsCave[],
  lat0: number,
  lonEast0: number,
  maxDeg = CAVE_FRAME_DEG,
) => {
  return caves.filter((cave) => {
    const dlat = cave.lat_deg - lat0
    const dlon = ((cave.lon_east_deg - lonEast0 + 540) % 360) - 180
    return Math.hypot(dlat, dlon) <= maxDeg
  })
}

export const spanForCaves = (caves: MarsCave[], lat0: number, lonEast0: number) => {
  const local = cavesInFrame(caves, lat0, lonEast0)
  if (local.length === 0) {
    return TERRAIN_SPAN_DEG
  }
  let span = 0.7
  for (const cave of local) {
    const dlat = Math.abs(cave.lat_deg - lat0)
    const dlon = Math.abs(((cave.lon_east_deg - lonEast0 + 540) % 360) - 180)
    span = Math.max(span, (dlat + 0.28) * 2, (dlon + 0.28) * 2)
  }
  return Math.min(span, 2.6)
}

export type CaveMarker = {
  id: string
  name: string
  x: number
  y: number
  z: number
  radiusM: number
  depthM: number
  roomRM: number
  best: boolean
}

export type HabitatBox = {
  x: number
  y: number
  z: number
  sx: number
  sy: number
  sz: number
  kind: "hub" | "wing" | "link" | "shaft"
}

export type HabitatPlan = {
  boxes: HabitatBox[]
  focusX: number
  focusY: number
  focusZ: number
}

export type LocalTerrain = {
  positions: Float32Array
  colors: Float32Array
  spanM: number
  minH: number
  maxH: number
  caves: CaveMarker[]
  habitat: HabitatPlan
}

export const layoutHabitat = (
  spanM: number,
  surfaceY: number,
  caves: CaveMarker[],
): HabitatPlan => {
  const unit = spanM * 0.016
  let cx = 0
  let cz = 0
  let surface = surfaceY
  let bury = Math.max(spanM * 0.02, unit * 1.3)
  if (caves.length > 0) {
    const home =
      caves.find((cave) => cave.best) ??
      caves.reduce((winner, cave) =>
        cave.roomRM > winner.roomRM ? cave : winner,
      )
    cx = home.x
    cz = home.z
    surface = home.y
    bury = home.depthM * 0.82
  }
  const floorY = surface - bury
  const hubH = unit * 0.72
  const wingH = unit * 0.55
  const linkH = unit * 0.28
  const boxes: HabitatBox[] = [
    {
      x: cx,
      y: floorY + hubH / 2,
      z: cz,
      sx: unit * 1.7,
      sy: hubH,
      sz: unit * 1.7,
      kind: "hub",
    },
  ]
  const wings = [
    { dx: unit * 2.5, dz: 0, sx: unit * 2.3, sz: unit * 0.72 },
    { dx: -unit * 2.5, dz: 0, sx: unit * 2.3, sz: unit * 0.72 },
    { dx: 0, dz: unit * 2.2, sx: unit * 0.72, sz: unit * 1.9 },
    { dx: 0, dz: -unit * 2.2, sx: unit * 0.72, sz: unit * 1.9 },
  ]
  for (const wing of wings) {
    boxes.push({
      x: cx + wing.dx,
      y: floorY + wingH / 2,
      z: cz + wing.dz,
      sx: wing.sx,
      sy: wingH,
      sz: wing.sz,
      kind: "wing",
    })
    boxes.push({
      x: cx + wing.dx * 0.48,
      y: floorY + linkH / 2,
      z: cz + wing.dz * 0.48,
      sx: wing.dx !== 0 ? unit * 0.95 : unit * 0.3,
      sy: linkH,
      sz: wing.dz !== 0 ? unit * 0.95 : unit * 0.3,
      kind: "link",
    })
  }
  const shaftH = bury + hubH
  boxes.push({
    x: cx + unit * 0.85,
    y: floorY + shaftH / 2,
    z: cz + unit * 0.85,
    sx: unit * 0.24,
    sy: shaftH,
    sz: unit * 0.24,
    kind: "shaft",
  })
  return { boxes, focusX: cx, focusY: floorY + hubH / 2, focusZ: cz }
}

const hash2 = (x: number, y: number) => {
  const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453
  return s - Math.floor(s)
}

const valueNoise = (x: number, y: number) => {
  const x0 = Math.floor(x)
  const y0 = Math.floor(y)
  const tx = x - x0
  const ty = y - y0
  const sx = tx * tx * (3 - 2 * tx)
  const sy = ty * ty * (3 - 2 * ty)
  const n00 = hash2(x0, y0)
  const n10 = hash2(x0 + 1, y0)
  const n01 = hash2(x0, y0 + 1)
  const n11 = hash2(x0 + 1, y0 + 1)
  return n00 * (1 - sx) * (1 - sy) + n10 * sx * (1 - sy) + n01 * (1 - sx) * sy + n11 * sx * sy
}

const fbm = (x: number, y: number) => {
  let amp = 1
  let freq = 1
  let sum = 0
  let norm = 0
  for (let i = 0; i < 5; i += 1) {
    sum += (valueNoise(x * freq, y * freq) * 2 - 1) * amp
    norm += amp
    amp *= 0.5
    freq *= 2.05
  }
  return sum / norm
}

const marsColor = (height: number, shade: number, cave: number) => {
  const t = Math.min(1, Math.max(0, (height + 4000) / 16000))
  let r = 92 + t * 110
  let g = 42 + t * 72
  let b = 24 + t * 38
  if (t > 0.82) {
    const ice = (t - 0.82) / 0.18
    r = r * (1 - ice) + 228 * ice
    g = g * (1 - ice) + 214 * ice
    b = b * (1 - ice) + 196 * ice
  }
  const lit = 0.38 + shade * 0.72
  r *= lit
  g *= lit
  b *= lit
  if (cave > 0.15) {
    r = r * (1 - cave) + 18 * cave
    g = g * (1 - cave) + 8 * cave
    b = b * (1 - cave) + 6 * cave
  }
  return [r / 255, g / 255, b / 255] as const
}

export const buildLocalTerrain = (
  grid: MolaGrid,
  lat0: number,
  lonEast0: number,
  caves: MarsCave[],
): LocalTerrain => {
  const cells = TERRAIN_CELLS
  const localCaves = cavesInFrame(caves, lat0, lonEast0)
  const spanDeg = spanForCaves(caves, lat0, lonEast0)
  const heights = new Float32Array((cells + 1) * (cells + 1))
  const caveMask = new Float32Array(heights.length)
  const metresPerDeg = 59000 * Math.cos((lat0 * Math.PI) / 180)
  const spanM = spanDeg * metresPerDeg

  for (let row = 0; row <= cells; row += 1) {
    const v = row / cells
    const lat = lat0 + (0.5 - v) * spanDeg
    for (let col = 0; col <= cells; col += 1) {
      const u = col / cells
      const lon = lonEast0 + (u - 0.5) * spanDeg
      let h = sampleMolaBilinear(grid, lat, lon)
      h += fbm(lon * 14, lat * 14) * 55
      h += fbm(lon * 40, lat * 40) * 18
      let caveAmt = 0
      for (const cave of localCaves) {
        const dlat = (lat - cave.lat_deg) * metresPerDeg
        const dlon = ((lon - cave.lon_east_deg + 540) % 360) - 180
        const dx = dlon * metresPerDeg
        const dist = Math.hypot(dlat, dx)
        const radius = Math.max(400, cave.diameter_m * 3)
        if (dist < radius) {
          const t = 1 - dist / radius
          const bowl = t * t * (3 - 2 * t)
          const depth = Math.max(cave.min_depth_m ?? 80, 80) * 2
          h -= depth * bowl
          caveAmt = Math.max(caveAmt, bowl)
        }
      }
      const i = row * (cells + 1) + col
      heights[i] = h
      caveMask[i] = caveAmt
    }
  }

  let minH = Infinity
  let maxH = -Infinity
  for (const h of heights) {
    if (h < minH) minH = h
    if (h > maxH) maxH = h
  }

  const positions = new Float32Array((cells + 1) * (cells + 1) * 3)
  const colors = new Float32Array((cells + 1) * (cells + 1) * 3)
  const exaggerate = 7.5
  const mid = (minH + maxH) / 2

  for (let row = 0; row <= cells; row += 1) {
    for (let col = 0; col <= cells; col += 1) {
      const i = row * (cells + 1) + col
      const x = (col / cells - 0.5) * spanM
      const z = (row / cells - 0.5) * spanM
      const y = (heights[i] - mid) * exaggerate
      positions[i * 3] = x
      positions[i * 3 + 1] = y
      positions[i * 3 + 2] = z

      const hL = heights[row * (cells + 1) + Math.max(0, col - 1)]
      const hR = heights[row * (cells + 1) + Math.min(cells, col + 1)]
      const hU = heights[Math.max(0, row - 1) * (cells + 1) + col]
      const hD = heights[Math.min(cells, row + 1) * (cells + 1) + col]
      const nx = hL - hR
      const nz = hU - hD
      const shade = Math.min(
        1,
        Math.max(0, 0.55 + (nx + nz) / 700 + (0.5 - caveMask[i])),
      )
      const [r, g, b] = marsColor(heights[i], shade, caveMask[i])
      colors[i * 3] = r
      colors[i * 3 + 1] = g
      colors[i * 3 + 2] = b
    }
  }

  const caveMarkers: CaveMarker[] = localCaves.map((cave) => {
    const x =
      (((cave.lon_east_deg - lonEast0 + 540) % 360) - 180) * metresPerDeg
    const z = (lat0 - cave.lat_deg) * metresPerDeg
    const col = Math.min(
      cells,
      Math.max(0, Math.round(((x / spanM) + 0.5) * cells)),
    )
    const row = Math.min(
      cells,
      Math.max(0, Math.round(((z / spanM) + 0.5) * cells)),
    )
    const i = row * (cells + 1) + col
    const surfaceY = (heights[i] - mid) * exaggerate
    const depthM = Math.max(
      (cave.min_depth_m ?? 80) * exaggerate * 2.4,
      spanM * 0.028,
    )
    return {
      id: cave.id,
      name: cave.name,
      x,
      y: surfaceY,
      z,
      radiusM: Math.max(cave.diameter_m * 2.4, spanM * 0.01),
      depthM,
      roomRM: Math.max(cave.diameter_m * 7, spanM * 0.02),
      best: cave.id === BEST_CAVE_ID,
    }
  })

  const midCell = Math.floor(cells / 2)
  const midIndex = midCell * (cells + 1) + midCell
  const surfaceY = (heights[midIndex] - mid) * exaggerate
  const habitat = layoutHabitat(spanM, surfaceY, caveMarkers)

  return { positions, colors, spanM, minH, maxH, caves: caveMarkers, habitat }
}
