import Link from "next/link"

export default function NotFound() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-3 bg-[#140c08] text-stone-100">
      <p className="text-sm text-stone-400">That landing area is not on the map.</p>
      <Link href="/" className="text-sm underline-offset-2 hover:underline">
        Back to map
      </Link>
    </div>
  )
}
