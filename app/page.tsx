import type { Metadata } from "next"

import { LandingPicker } from "@/components/landing-picker"

export const metadata: Metadata = {
  title: "NASA landing areas — Mars City",
  description: "Click a NASA landing area to inspect terrain and cave pits.",
}

export default function Page() {
  return <LandingPicker />
}
