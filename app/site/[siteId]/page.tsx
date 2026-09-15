import type { Metadata } from "next"
import { notFound } from "next/navigation"

import { SiteInspect } from "@/components/site-inspect"
import sitesPayload from "@/data/processed/sites_scored.json"
import { NASA_AREA_BY_ID, NASA_SITE_IDS } from "@/lib/nasa-areas"

type PageProps = {
  params: Promise<{ siteId: string }>
  searchParams: Promise<{ lat?: string; lon?: string }>
}

export const generateStaticParams = () => {
  return [...NASA_SITE_IDS, "custom"].map((siteId) => ({ siteId }))
}

export const generateMetadata = async ({
  params,
}: PageProps): Promise<Metadata> => {
  const { siteId } = await params
  if (siteId === "custom") {
    return {
      title: "Custom site — Mars City",
      description: "Inspect a custom Mars landing pin.",
    }
  }
  const site = sitesPayload.sites.find((item) => item.id === siteId)
  const area = NASA_AREA_BY_ID[siteId]
  return {
    title: `${site?.name ?? siteId} — Mars City`,
    description: area?.source ?? site?.why_it_matters,
  }
}

const parseCoord = (value: string | undefined) => {
  if (!value) {
    return undefined
  }
  const next = Number.parseFloat(value)
  return Number.isFinite(next) ? next : undefined
}

export default async function Page({ params, searchParams }: PageProps) {
  const { siteId } = await params
  const query = await searchParams

  if (siteId === "custom") {
    const lat_deg = parseCoord(query.lat)
    const lon_east_deg = parseCoord(query.lon)
    if (lat_deg == null || lon_east_deg == null) {
      notFound()
    }
    return (
      <SiteInspect
        siteId="custom"
        lat_deg={lat_deg}
        lon_east_deg={lon_east_deg}
      />
    )
  }

  const area = NASA_AREA_BY_ID[siteId]
  if (!area) {
    notFound()
  }

  const site = sitesPayload.sites.find((item) => item.id === siteId)
  if (!site) {
    notFound()
  }

  return (
    <SiteInspect
      siteId={site.id}
      lat_deg={site.lat_deg}
      lon_east_deg={site.lon_east_deg}
    />
  )
}
