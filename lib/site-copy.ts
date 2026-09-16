import type { LandingSite } from "@/lib/mars-landing"
import type { SitePhysics } from "@/lib/site-physics"

export type SiteCopy = {
  headline: string
  detail: string
}

const metres = (value: number) => {
  const rounded = Math.round(value * 10) / 10
  if (Number.isInteger(rounded)) {
    return `${rounded}`
  }
  return rounded.toFixed(1)
}

export const siteCopy = (report: SitePhysics, site?: LandingSite): SiteCopy => {
  if (report.cave.coversRadiation && report.cave.nearest) {
    return {
      headline: `Use ${report.cave.nearest.name}.`,
      detail: `Roof already beats a dirt pile. Best pit on this map.`,
    }
  }

  const buryM = Math.max(report.shieldingDepthM, report.thermal.annualSkinM)
  if (buryM <= 0.3) {
    return {
      headline: "Build on the surface.",
      detail: "Keep a flare closet. No published cave here.",
    }
  }

  const iceHint =
    site?.ice_0_1m != null && site.ice_0_1m >= 0.25
      ? " Ice in the first metre."
      : site?.ice_1_5m != null && site.ice_1_5m >= 0.4
        ? " Ice below a metre."
        : ""
  return {
    headline: `Bury ${metres(buryM)} m.`,
    detail: `No cave roof here. Arsia / Annie is the better pick.${iceHint}`,
  }
}
