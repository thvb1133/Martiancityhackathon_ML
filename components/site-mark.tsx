"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"

import { formatLatLon } from "@/lib/mars-landing"
import { ROLE_DOT, type NasaAreaRole } from "@/lib/nasa-areas"
import { cn } from "@/lib/utils"

export type SiteMarkProps = {
  href: string
  name: string
  lat_deg: number
  lon_east_deg: number
  fact: string
  role?: NasaAreaRole | "custom"
  selected?: boolean
  recommended?: boolean
  compact?: boolean
  className?: string
  style?: React.CSSProperties
}

export const SiteMark = ({
  href,
  name,
  lat_deg,
  lon_east_deg,
  fact,
  role = "shortlist",
  selected = false,
  recommended = false,
  compact = false,
  className,
  style,
}: SiteMarkProps) => {
  const router = useRouter()
  const coords = formatLatLon(lat_deg, lon_east_deg)
  const handleClick = (event: React.MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault()
    event.stopPropagation()
    router.push(href)
  }

  return (
    <Link
      href={href}
      prefetch
      aria-label={`Inspect ${name}${recommended ? ", recommended" : ""}. ${coords}. ${fact}`}
      aria-pressed={selected}
      className={cn(
        "group relative pointer-events-auto inline-flex items-center gap-1 whitespace-nowrap rounded-full text-[10px] leading-tight",
        compact ? "size-6 justify-center p-0" : "px-1.5 py-0.5",
        recommended
          ? "bg-stone-950/90 text-[#fff6ea] ring-2 ring-teal-300"
          : selected
            ? "bg-stone-950/90 text-[#fff6ea] ring-1 ring-[#fff6ea]"
            : "bg-stone-950/75 text-[#fff6ea]",
        className,
      )}
      style={style}
      onPointerDown={(event) => {
        event.stopPropagation()
      }}
      onClick={handleClick}
    >
      <span
        aria-hidden
        className={cn("size-1.5 shrink-0 rounded-full", ROLE_DOT[role])}
      />
      <span className={compact ? "sr-only" : undefined}>{name}</span>
      {recommended ? (
        <span className="font-medium text-teal-200">Best</span>
      ) : null}
      <span
        role="tooltip"
        className="invisible absolute bottom-full left-1/2 z-50 mb-1 w-max max-w-48 -translate-x-1/2 rounded-md bg-foreground px-2 py-1.5 text-left text-[10px] leading-snug text-background group-hover:visible group-focus-visible:visible"
      >
        <span className="block font-mono">{coords}</span>
        <span className="mt-0.5 block">{fact}</span>
      </span>
    </Link>
  )
}
