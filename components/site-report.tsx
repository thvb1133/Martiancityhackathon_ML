import { Badge } from "@/components/ui/badge"
import type { MarsCave } from "@/lib/mars-caves"
import type { LandingPick, LandingSite } from "@/lib/mars-landing"
import {
  INSIGHT_EVENTS,
  INSIGHT_MAX_MW,
  evaluateSite,
} from "@/lib/site-physics"

export type SiteReportProps = {
  site?: LandingSite
  pick: LandingPick
  elevationM: number | null
  caves: MarsCave[]
}

const formatIce = (value: number | null) => {
  if (value == null) {
    return "—"
  }
  return value.toFixed(2)
}

const formatElev = (metres: number) => {
  const rounded = Math.round(metres)
  return `${rounded >= 0 ? "+" : ""}${rounded.toLocaleString()} m`
}

export const SiteReport = ({
  site,
  pick,
  elevationM,
  caves,
}: SiteReportProps) => {
  if (elevationM == null) {
    return (
      <p className="mt-2 text-sm text-stone-400" aria-live="polite">
        Sampling elevation…
      </p>
    )
  }

  const report = evaluateSite(
    elevationM,
    pick.lat_deg,
    pick.lon_east_deg,
    caves,
  )

  return (
    <div className="mt-3 space-y-3 text-sm">
      {site ? (
        <p className="text-stone-300">{site.why_it_matters}</p>
      ) : (
        <p className="text-stone-400">
          Terrain is MOLA, upsampled, with local roughness added so the ground
          reads at this scale.
        </p>
      )}

      <div className="flex items-center gap-2">
        <h2 className="text-xs font-medium tracking-wide text-stone-400 uppercase">
          Site report
        </h2>
        <Badge
          variant="outline"
          className="border-white/25 text-stone-300"
        >
          model estimate
        </Badge>
      </div>

      <section aria-labelledby="report-radiation">
        <h3 id="report-radiation" className="font-medium text-stone-100">
          Radiation
        </h3>
        <p className="mt-0.5 text-stone-300">
          {report.surfaceDoseMsvPerSol.toFixed(2)} mSv/sol at the surface. Dig{" "}
          <span className="text-stone-100">
            {report.shieldingDepthM.toFixed(1)} m
          </span>{" "}
          of regolith for a 20 mSv/yr worker budget. SEP storm shelter:{" "}
          {report.sepShelterDepthM.toFixed(2)} m.
        </p>
        <p className="mt-0.5 text-stone-400">{report.cave.note}</p>
      </section>

      <section aria-labelledby="report-quakes">
        <h3 id="report-quakes" className="font-medium text-stone-100">
          Marsquakes
        </h3>
        <p className="mt-0.5 text-stone-300">
          {report.seismic.tier} · {Math.round(report.seismic.distanceKm).toLocaleString()}{" "}
          km from Cerberus Fossae. InSight: &gt;{INSIGHT_EVENTS.toLocaleString()}{" "}
          events, max M{INSIGHT_MAX_MW}.
        </p>
        <p className="mt-0.5 text-stone-400">
          Ground shaking is not the limiter. The real risk is lava-tube roof
          stability.
        </p>
      </section>

      <section aria-labelledby="report-wind">
        <h3 id="report-wind" className="font-medium text-stone-100">
          Wind load
        </h3>
        <p className="mt-0.5 text-stone-300">
          Storm median {report.wind.stormMedianPa.toFixed(1)} Pa · peak{" "}
          {report.wind.peakPa.toFixed(1)} Pa at {report.wind.peakMs.toFixed(0)}{" "}
          m/s. Earth at that speed: {report.wind.earthPeakPa.toFixed(0)} Pa.
        </p>
        <p className="mt-0.5 text-stone-400">
          Wind does not limit height. Pressurisation and dust do.
        </p>
      </section>

      <section aria-labelledby="report-thermal">
        <h3 id="report-thermal" className="font-medium text-stone-100">
          Thermal
        </h3>
        <p className="mt-0.5 text-stone-300">
          Annual skin depth {report.thermal.annualSkinM.toFixed(1)} m, then a
          steady {Math.round(report.thermal.meanTempC)} °C. 5 m of geothermal
          gain: {report.thermal.geothermalGain5mK.toFixed(2)} K.
        </p>
        <p className="mt-0.5 text-stone-400">
          Dig {report.thermal.annualSkinM.toFixed(1)} m for thermal stability,
          not heat. Heat the volume with 100-person waste heat.
        </p>
      </section>

      <section aria-labelledby="report-ground">
        <h3 id="report-ground" className="font-medium text-stone-100">
          Ground
        </h3>
        <p className="mt-0.5 text-stone-300">
          {formatElev(elevationM)}
          {site?.slope_deg_local != null
            ? ` · slope ${site.slope_deg_local.toFixed(1)}°`
            : ""}
        </p>
        <p className="mt-0.5 text-stone-400">
          SWIM ice consistency 0–1 m {formatIce(site?.ice_0_1m ?? null)} · 1–5 m{" "}
          {formatIce(site?.ice_1_5m ?? null)} · &gt;5 m{" "}
          {formatIce(site?.ice_gt_5m ?? null)}. Dust storm sols 180–260. 100
          people, 730 sols to resupply.
        </p>
      </section>

      <p className="text-xs text-stone-500">
        Physics rules with cited constants, not measured site data. Wind series
        is Track A (simulated, Jezero).
      </p>
    </div>
  )
}
