"use client"

import Link from "next/link"

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip"
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
  className,
  style,
}: SiteMarkProps) => {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Link
            href={href}
            aria-label={`Inspect ${name}`}
            aria-pressed={selected}
            className={cn(
              "pointer-events-auto inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] leading-tight",
              selected
                ? "bg-stone-950/90 text-[#fff6ea] ring-1 ring-[#fff6ea]"
                : "bg-stone-950/75 text-[#fff6ea]",
              className,
            )}
            style={style}
            onPointerDown={(event) => {
              event.stopPropagation()
            }}
          />
        }
      >
        <span
          aria-hidden
          className={cn("size-1.5 shrink-0 rounded-full", ROLE_DOT[role])}
        />
        {name}
      </TooltipTrigger>
      <TooltipContent
        side="top"
        className="flex max-w-52 flex-col items-start gap-1 text-left"
      >
        <p className="font-mono text-[11px]">
          {formatLatLon(lat_deg, lon_east_deg)}
        </p>
        <p>{fact}</p>
      </TooltipContent>
    </Tooltip>
  )
}
