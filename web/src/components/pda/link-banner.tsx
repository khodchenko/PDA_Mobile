import { CircleAlert, Loader2, Skull, WifiOff } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import type { Chain } from "@/lib/link"
import type { FastSnapshot } from "@/lib/protocol"
import { cn } from "@/lib/utils"

/** Explains, in place, why the numbers below may be old or missing. */
export function LinkBanner({ chain, fast }: { chain: Chain; fast: FastSnapshot | null }) {
  const { overall } = chain
  if (overall.tone === "ok") return null
  const Icon =
    fast?.game_state === "dead" && overall.stage === "game"
      ? Skull
      : overall.tone === "idle"
        ? Loader2
        : overall.stage === "bridge" || overall.stage === "phone"
          ? WifiOff
          : CircleAlert
  return (
    <Alert
      variant={overall.tone === "bad" ? "destructive" : "default"}
      className={cn(overall.tone === "warn" && "border-primary/40 text-primary")}
    >
      <Icon className={cn(overall.tone === "idle" && "animate-spin")} />
      <AlertTitle>{overall.title}</AlertTitle>
      <AlertDescription>{overall.detail}</AlertDescription>
    </Alert>
  )
}
