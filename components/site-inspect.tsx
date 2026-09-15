"use client"

import { useEffect, useMemo, useState } from "react"
import dynamic from "next/dynamic"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { SiteReport } from "@/components/site-report"
import { cavesNear } from "@/lib/mars-caves"
import {
  formatLatLon,
  type LandingPick,
  type LandingSite,
} from "@/lib/mars-landing"
import {
  loadMola4ppd,
  sampleMolaBilinear,
} from "@/lib/mola-heightmap"
import { NASA_AREA_BY_ID } from "@/lib/nasa-areas"

const SiteTerrain = dynamic(
  () => import("@/components/site-terrain").then((mod) => mod.SiteTerrain),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center text-sm text-stone-400">
        Building terrain…
      </div>
    ),
  },
)

export type SiteInspectProps = {
  siteId: string
  lat_deg: number
  lon_east_deg: number
}

export const SiteInspect = ({
  siteId,
  lat_deg,
  lon_east_deg,
}: SiteInspectProps) => {
  const router = useRouter()
  const [site, setSite] = useState<LandingSite>()
  const [elevationM, setElevationM] = useState<number | null>(null)
  const pick = useMemo<LandingPick>(
    () => ({ lat_deg, lon_east_deg, siteId }),
    [lat_deg, lon_east_deg, siteId],
  )
  const nearbyCaves = useMemo(
    () => cavesNear(lat_deg, lon_east_deg, 4),
    [lat_deg, lon_east_deg],
  )
  const isCustom = siteId === "custom"
  const area = NASA_AREA_BY_ID[siteId]

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
      <div className="absolute inset-0">
        <SiteTerrain
          lat_deg={lat_deg}
          lon_east_deg={lon_east_deg}
          caves={nearbyCaves}
        />
      </div>

      <header className="pointer-events-none absolute inset-x-0 top-0 z-30 p-4 sm:p-6">
        <h1 className="text-xl font-medium tracking-tight sm:text-2xl">
          {site?.name ?? (isCustom ? "Custom site" : area ? siteId : "Site")}
        </h1>
      </header>

      <aside className="pointer-events-none absolute bottom-0 left-0 z-30 w-full p-4 sm:max-w-md sm:p-6">
        <div className="pointer-events-auto max-h-[60svh] overflow-y-auto rounded-lg bg-black/70 p-4 backdrop-blur-sm">
          <div className="flex items-start justify-between gap-3">
            <p className="font-mono text-sm">
              {formatLatLon(lat_deg, lon_east_deg)}
            </p>
            <Link
              href="/"
              className="text-sm text-stone-300 underline-offset-2 hover:underline"
            >
              Back to map
            </Link>
          </div>
          <SiteReport
            site={site}
            pick={pick}
            elevationM={site?.elevation_m ?? elevationM}
            caves={nearbyCaves}
          />
        </div>
      </aside>
    </div>
  )
}
