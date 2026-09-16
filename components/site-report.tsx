import { SettlementSparkline } from "@/components/settlement-sparkline"
import type { MarsCave } from "@/lib/mars-caves"
import type { LandingPick, LandingSite } from "@/lib/mars-landing"
import { analyseSite } from "@/lib/site-analysis"
import { evaluateSite } from "@/lib/site-physics"

export type SiteReportProps = {
  site?: LandingSite
  pick: LandingPick
  elevationM: number | null
  caves: MarsCave[]
}

export const SiteReport = ({
  site,
  pick,
  elevationM,
  caves,
}: SiteReportProps) => {
  if (elevationM == null) {
    return (
      <p className="mt-4 text-sm text-stone-400" aria-live="polite">
        Sampling elevation…
      </p>
    )
  }

  const analysis = analyseSite(
    evaluateSite(elevationM, pick.lat_deg, pick.lon_east_deg, caves),
    pick.lat_deg,
    pick.lon_east_deg,
    site
  )

  return (
    <div
      className="mt-5 space-y-4 text-sm leading-relaxed text-stone-300"
      aria-live="polite"
    >
      <p className="text-2xl font-medium tracking-tight text-stone-100">
        {analysis.verdict}
      </p>
      <p className="font-mono text-xs text-stone-400">{analysis.facts}</p>
      {analysis.lead ? <p>{analysis.lead}</p> : null}

      <dl>
        {analysis.rows.map((row) => (
          <div
            key={row.label}
            className="flex justify-between gap-4 border-t border-white/10 py-1.5 first:border-t-0"
          >
            <dt className="text-stone-400">{row.label}</dt>
            <dd className="font-mono text-stone-100">{row.value}</dd>
          </div>
        ))}
      </dl>

      <div className="space-y-3">
        {analysis.showSparkline ? <SettlementSparkline /> : null}
        <p>{analysis.storm}</p>
      </div>
      <p>{analysis.water}</p>
      <p>{analysis.dig}</p>
    </div>
  )
}
