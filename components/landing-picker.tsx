"use client"

import { useEffect, useMemo, useState, type ComponentType } from "react"
import { useRouter } from "next/navigation"

import { MarsMap2D } from "@/components/mars-map-2d"
import type { MarsGlobeProps } from "@/components/mars-globe"
import { AREA_GROUPS, NASA_SITE_IDS, ROLE_DOT } from "@/lib/nasa-areas"
import {
  JEZERO,
  customSiteHref,
  siteHref,
  type CustomSite,
  type LandingPick,
  type LandingSite,
} from "@/lib/mars-landing"
import { cn } from "@/lib/utils"

export const LandingPicker = () => {
  const router = useRouter()
  const [sites, setSites] = useState<LandingSite[]>([])
  const [customSites, setCustomSites] = useState<CustomSite[]>([])
  const [pick, setPick] = useState<LandingPick>(JEZERO)
  const [Globe, setGlobe] = useState<ComponentType<MarsGlobeProps> | null>(null)
  const [globeReady, setGlobeReady] = useState(false)

  const nasaSites = useMemo(
    () => sites.filter((site) => NASA_SITE_IDS.includes(site.id)),
    [sites]
  )

  const handleInspect = (next: LandingPick) => {
    setPick(next)
    if (!next.siteId) {
      return
    }
    router.push(siteHref(next.siteId, next.lat_deg, next.lon_east_deg))
  }

  const handleGlobeReady = () => {
    setGlobeReady(true)
  }

  const handleFail = () => {
    setGlobe(null)
    setGlobeReady(false)
  }

  const handleCustomAdd = (lat_deg: number, lon_east_deg: number) => {
    setCustomSites((current) => [
      ...current,
      { id: `custom-${Date.now()}`, lat_deg, lon_east_deg },
    ])
    router.push(customSiteHref(lat_deg, lon_east_deg))
  }

  useEffect(() => {
    const handleLoad = async () => {
      const response = await fetch("/data/sites_scored.json")
      if (!response.ok) {
        return
      }
      const payload = (await response.json()) as { sites: LandingSite[] }
      setSites(payload.sites)
    }
    void handleLoad()
  }, [])

  useEffect(() => {
    let cancelled = false
    const timer = window.setTimeout(() => {
      void import("@/components/mars-globe")
        .then((mod) => {
          if (cancelled) {
            return
          }
          setGlobe(() => mod.MarsGlobe)
        })
        .catch(() => {
          if (!cancelled) {
            setGlobe(null)
          }
        })
    }, 0)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [])

  return (
    <div className="relative min-h-svh bg-[#140c08] text-stone-100">
      <div
        className="absolute inset-0"
        role="application"
        aria-label="Mars map of NASA landing areas and cave pits. Click a label or cave to inspect. Long-press to add a custom site."
      >
        <MarsMap2D
          pick={pick}
          sites={nasaSites}
          customSites={customSites}
          onPick={handleInspect}
          onCustomAdd={handleCustomAdd}
        />
        {Globe ? (
          <div className={cn("absolute inset-0", !globeReady && "invisible")}>
            <Globe
              pick={pick}
              sites={nasaSites}
              customSites={customSites}
              onPick={handleInspect}
              onCustomAdd={handleCustomAdd}
              onReady={handleGlobeReady}
              onFail={handleFail}
            />
          </div>
        ) : null}
      </div>

      <header className="pointer-events-none absolute inset-x-0 top-0 z-10 p-4 sm:p-6">
        <h1 className="text-xl font-medium tracking-tight sm:text-2xl">
          NASA landing areas
        </h1>
      </header>

      <aside className="pointer-events-none absolute bottom-0 left-0 z-10 w-full p-4 sm:max-w-xs sm:p-6">
        <div className="pointer-events-auto rounded-lg bg-black/70 p-3 backdrop-blur-sm">
          <ul className="flex flex-wrap gap-x-3 gap-y-1.5 text-[10px] text-stone-300">
            {AREA_GROUPS.map((group) => (
              <li key={group.label} className="flex items-center gap-1.5">
                <span
                  aria-hidden
                  className={`size-1.5 rounded-full ${ROLE_DOT[group.roles[0]]}`}
                />
                {group.label}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-stone-400">
            100 people · 730 sols · storm 180–260. Teal is Arsia / Annie.
          </p>
        </div>
      </aside>
    </div>
  )
}
