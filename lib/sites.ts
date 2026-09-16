import sitesPayload from "@/public/data/sites_scored.json"

import type { LandingSite } from "@/lib/mars-landing"

export const scoredSites = sitesPayload.sites as LandingSite[]

export const scoredSiteById = (siteId: string) => {
  return scoredSites.find((site) => site.id === siteId)
}
