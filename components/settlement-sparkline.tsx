import { SETTLEMENT, sparklineLabel } from "@/lib/settlement"

const WIDTH = 280
const HEIGHT = 48

export const SettlementSparkline = () => {
  const { series, storm } = SETTLEMENT
  const values = series.solar
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const lastSol = series.sols[series.sols.length - 1] ?? 729
  const last = values.length - 1

  const points = values.map((value, index) => {
    const x = (index / Math.max(last, 1)) * WIDTH
    const y = HEIGHT - ((value - min) / span) * (HEIGHT - 8) - 4
    return { x, y }
  })
  const line = points
    .map((point, index) => {
      const command = index === 0 ? "M" : "L"
      return `${command}${point.x.toFixed(1)},${point.y.toFixed(1)}`
    })
    .join(" ")
  const area = `${line} L${WIDTH},${HEIGHT} L0,${HEIGHT} Z`

  const stormX = (storm.startSol / lastSol) * WIDTH
  const stormW = ((storm.endSol - storm.startSol) / lastSol) * WIDTH

  return (
    <svg
      role="img"
      aria-label={sparklineLabel()}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="h-12 w-full text-orange-300"
    >
      <rect
        x={stormX.toFixed(1)}
        y="0"
        width={stormW.toFixed(1)}
        height={HEIGHT}
        className="fill-red-500/25"
      />
      <path d={area} className="fill-orange-400/20" />
      <path
        d={line}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
    </svg>
  )
}
