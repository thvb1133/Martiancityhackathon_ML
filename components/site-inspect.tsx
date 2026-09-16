"use client"

import { useEffect, useMemo, useState } from "react"
import dynamic from "next/dynamic"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { SiteReport } from "@/components/site-report"
import { caveFact, cavesNear, nearestCave } from "@/lib/mars-caves"
import {
  formatLatLon,
  type LandingPick,
  type LandingSite,
} from "@/lib/mars-landing"
import { loadMola4ppd, sampleMolaBilinear } from "@/lib/mola-heightmap"

const SiteTerrain = dynamic(
  () => import("@/components/site-terrain").then((mod) => mod.SiteTerrain),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-sm text-stone-400">
        Building terrain…
      </div>
    ),
  }
)

export type SiteInspectProps = {
  siteId: string
  lat_deg: number
  lon_east_deg: number
  initialSite?: LandingSite
}

export const SiteInspect = ({
  siteId,
  lat_deg,
  lon_east_deg,
  initialSite,
}: SiteInspectProps) => {
  const router = useRouter()
  const [site, setSite] = useState<LandingSite | undefined>(initialSite)
  const [elevationM, setElevationM] = useState<number | null>(
    initialSite?.elevation_m ?? null
  )
  const pick = useMemo<LandingPick>(
    () => ({ lat_deg, lon_east_deg, siteId }),
    [lat_deg, lon_east_deg, siteId]
  )
  const nearbyCaves = useMemo(
    () => cavesNear(lat_deg, lon_east_deg, 4),
    [lat_deg, lon_east_deg]
  )
  const namedCave = useMemo(
    () => nearestCave(lat_deg, lon_east_deg),
    [lat_deg, lon_east_deg]
  )
  const reportSite = useMemo<LandingSite | undefined>(() => {
    if (!namedCave) {
      return site
    }
    return {
      id: namedCave.id,
      name: namedCave.name,
      lat_deg: namedCave.lat_deg,
      lon_east_deg: namedCave.lon_east_deg,
      archetype: "lava_tube",
      why_it_matters: caveFact(namedCave),
      tracks: "architecture",
      elevation_m: site?.elevation_m ?? null,
      slope_deg_local: site?.slope_deg_local ?? null,
      ice_0_1m: site?.ice_0_1m ?? null,
      ice_1_5m: site?.ice_1_5m ?? null,
      ice_gt_5m: site?.ice_gt_5m ?? null,
    }
  }, [namedCave, site])
  const isCustom = siteId === "custom"
  const title =
    namedCave?.name ?? site?.name ?? (isCustom ? "Custom site" : "Site")

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        router.push("/")
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [router])

  useEffect(() => {
    if (isCustom) {
      return
    }
    const handleLoad = async () => {
      const response = await fetch("/data/sites_scored.json")
      if (!response.ok) {
        return
      }
      const payload = (await response.json()) as { sites: LandingSite[] }
      setSite(payload.sites.find((item) => item.id === siteId))
    }
    void handleLoad()
  }, [isCustom, siteId])

  useEffect(() => {
    let cancelled = false
    const handleSample = async () => {
      const grid = await loadMola4ppd()
      if (cancelled) {
        return
      }
      setElevationM(sampleMolaBilinear(grid, lat_deg, lon_east_deg))
    }
    void handleSample()
    return () => {
      cancelled = true
    }
  }, [lat_deg, lon_east_deg])

  return (
    <div className="relative min-h-svh bg-[#140c08] text-stone-100">
      <div className="absolute inset-0 lg:left-[28rem]">
        <SiteTerrain
          lat_deg={lat_deg}
          lon_east_deg={lon_east_deg}
          caves={nearbyCaves}
        />
      </div>

      <aside
        className="absolute inset-x-0 bottom-0 z-30 max-h-[62vh] overflow-y-auto overscroll-contain bg-gradient-to-t from-[#140c08] via-[#140c08]/95 to-[#140c08]/80 p-4 sm:p-6 lg:inset-y-0 lg:right-auto lg:left-0 lg:max-h-none lg:w-[28rem] lg:bg-[#140c08]"
        aria-label="Site analysis"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-medium tracking-tight sm:text-2xl">
              {title}
            </h1>
            <p className="mt-1 font-mono text-sm text-stone-400">
              {formatLatLon(lat_deg, lon_east_deg)}
            </p>
          </div>
          <Link
            href="/"
            className="shrink-0 pt-1 text-sm text-stone-300 underline-offset-2 hover:underline"
            onClick={(event) => {
              event.preventDefault()
              router.push("/")
            }}
          >
            Map
          </Link>
        </div>
        <SiteReport
          site={reportSite}
          pick={pick}
          elevationM={elevationM ?? site?.elevation_m ?? null}
          caves={nearbyCaves}
        />
      </aside>
    </div>
  )
}
