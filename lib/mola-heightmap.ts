const COLS = 1440
const ROWS = 720

export type MolaGrid = {
  cols: number
  rows: number
  elev: Float32Array
}

export const loadMola4ppd = async (): Promise<MolaGrid> => {
  const response = await fetch("/data/mola_4ppd.i16")
  if (!response.ok) {
    throw new Error("MOLA heightmap missing")
  }
  const buffer = await response.arrayBuffer()
  const view = new DataView(buffer)
  const count = buffer.byteLength / 2
  const elev = new Float32Array(count)
  for (let i = 0; i < count; i += 1) {
    const raw = view.getInt16(i * 2, false)
    elev[i] = raw === -32768 ? 0 : raw
  }
  return { cols: COLS, rows: ROWS, elev }
}

const wrapCol = (col: number, cols: number) => {
  return ((col % cols) + cols) % cols
}

const clampRow = (row: number, rows: number) => {
  return Math.min(rows - 1, Math.max(0, row))
}

const elevAt = (grid: MolaGrid, row: number, col: number) => {
  return grid.elev[clampRow(row, grid.rows) * grid.cols + wrapCol(col, grid.cols)] ?? 0
}

export const sampleMolaMetres = (
  grid: MolaGrid,
  latDeg: number,
  lonEastDeg: number,
) => {
  const east = ((lonEastDeg % 360) + 360) % 360
  const col = Math.round((east / 360) * grid.cols)
  const row = Math.round(((90 - latDeg) / 180) * (grid.rows - 1))
  return elevAt(grid, row, col)
}

export const sampleMolaBilinear = (
  grid: MolaGrid,
  latDeg: number,
  lonEastDeg: number,
) => {
  const east = ((lonEastDeg % 360) + 360) % 360
  const colF = (east / 360) * grid.cols
  const rowF = ((90 - latDeg) / 180) * (grid.rows - 1)
  const col0 = Math.floor(colF)
  const row0 = Math.floor(rowF)
  const tx = colF - col0
  const ty = rowF - row0
  const h00 = elevAt(grid, row0, col0)
  const h10 = elevAt(grid, row0, col0 + 1)
  const h01 = elevAt(grid, row0 + 1, col0)
  const h11 = elevAt(grid, row0 + 1, col0 + 1)
  return h00 * (1 - tx) * (1 - ty) + h10 * tx * (1 - ty) + h01 * (1 - tx) * ty + h11 * tx * ty
}
