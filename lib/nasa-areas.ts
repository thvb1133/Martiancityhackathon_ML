export type NasaAreaRole = "landed" | "human_ez" | "cave_shelter" | "shortlist"

export type NasaArea = {
  siteId: string
  role: NasaAreaRole
  source: string
  ellipseKm: [number, number]
  headingDeg: number
}

export const NASA_AREAS: NasaArea[] = [
  {
    siteId: "jezero",
    role: "landed",
    source: "Perseverance, 2021. Nili Fossae human exploration zone.",
    ellipseKm: [8, 7],
    headingDeg: 96,
  },
  {
    siteId: "gale",
    role: "landed",
    source: "Curiosity, 2012. Long REMS weather record.",
    ellipseKm: [20, 7],
    headingDeg: 107,
  },
  {
    siteId: "oxia",
    role: "landed",
    source: "ExoMars Rosalind Franklin landing region. NASA/ESA.",
    ellipseKm: [120, 20],
    headingDeg: 90,
  },
  {
    siteId: "mawrth",
    role: "shortlist",
    source: "Repeated NASA/ESA landing shortlist. Clay-bearing.",
    ellipseKm: [80, 40],
    headingDeg: 70,
  },
  {
    siteId: "arcadia",
    role: "human_ez",
    source: "2015 human exploration zone. SWIM ice belt.",
    ellipseKm: [100, 80],
    headingDeg: 0,
  },
  {
    siteId: "deuteronilus",
    role: "human_ez",
    source: "2015 human exploration zone. Debris-covered ice.",
    ellipseKm: [90, 70],
    headingDeg: 15,
  },
  {
    siteId: "phlegra",
    role: "human_ez",
    source: "2015 human exploration zone. Mid-latitude ice plus relief.",
    ellipseKm: [80, 60],
    headingDeg: 20,
  },
  {
    siteId: "acidalia",
    role: "human_ez",
    source: "2015 human exploration zone. Northern lowlands.",
    ellipseKm: [100, 80],
    headingDeg: 0,
  },
  {
    siteId: "valles",
    role: "human_ez",
    source: "Melas Chasma exploration zone. Canyon shelter, hard EDL.",
    ellipseKm: [70, 30],
    headingDeg: 95,
  },
  {
    siteId: "hellas",
    role: "shortlist",
    source: "Deepest large basin. Highest surface pressure.",
    ellipseKm: [120, 90],
    headingDeg: 0,
  },
  {
    siteId: "isidis",
    role: "shortlist",
    source: "Low basin next to Jezero. Logistics hub case.",
    ellipseKm: [90, 70],
    headingDeg: 0,
  },
  {
    siteId: "meridiani",
    role: "landed",
    source: "Opportunity, 2004. Flat hematite plain.",
    ellipseKm: [80, 12],
    headingDeg: 80,
  },
  {
    siteId: "elysium",
    role: "landed",
    source: "InSight, 2018. Flat volcanic plains.",
    ellipseKm: [130, 27],
    headingDeg: 90,
  },
  {
    siteId: "chryse",
    role: "landed",
    source: "Viking 1, 1976. First successful landing.",
    ellipseKm: [100, 40],
    headingDeg: 70,
  },
  {
    siteId: "utopia",
    role: "landed",
    source: "Viking 2, 1976. Ice-rich northern basin.",
    ellipseKm: [100, 40],
    headingDeg: 70,
  },
  {
    siteId: "arsia",
    role: "cave_shelter",
    source: "THEMIS cave skylights. Radiation-shelter case, high and hard to land.",
    ellipseKm: [80, 50],
    headingDeg: 30,
  },
  {
    siteId: "pavonis",
    role: "cave_shelter",
    source: "Tharsis tube-fed flows. Published pits sit on Arsia, south of here.",
    ellipseKm: [60, 40],
    headingDeg: 25,
  },
]

export const NASA_AREA_BY_ID = Object.fromEntries(
  NASA_AREAS.map((area) => [area.siteId, area]),
) as Record<string, NasaArea>

export const NASA_SITE_IDS = NASA_AREAS.map((area) => area.siteId)

export const ROLE_LABEL: Record<NasaAreaRole, string> = {
  landed: "NASA landed",
  human_ez: "Human exploration zone",
  cave_shelter: "Cave shelter",
  shortlist: "Landing shortlist",
}

export const AREA_GROUPS: { label: string; roles: NasaAreaRole[] }[] = [
  { label: "Human exploration zones", roles: ["human_ez"] },
  { label: "Flown landings", roles: ["landed"] },
  { label: "Cave shelter", roles: ["cave_shelter"] },
  { label: "Also shortlisted", roles: ["shortlist"] },
]

export const ROLE_DOT: Record<NasaAreaRole | "custom", string> = {
  human_ez: "bg-sky-400",
  landed: "bg-stone-100",
  cave_shelter: "bg-teal-300",
  shortlist: "bg-amber-300",
  custom: "bg-orange-300",
}
