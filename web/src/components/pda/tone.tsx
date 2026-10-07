import { cn } from "@/lib/utils"
import type { Tone } from "@/lib/link"

const toneDot: Record<Tone, string> = {
  ok: "bg-chart-1 shadow-[0_0_10px] shadow-chart-1/70",
  warn: "bg-primary shadow-[0_0_10px] shadow-primary/60",
  bad: "bg-destructive shadow-[0_0_10px] shadow-destructive/60",
  idle: "bg-muted-foreground/60",
}

export function ToneDot({ tone, pulse, className }: { tone: Tone; pulse?: boolean; className?: string }) {
  return (
    <span className={cn("relative inline-flex size-2.5 shrink-0", className)} aria-hidden>
      {pulse && <span className={cn("absolute inset-0 animate-ping rounded-full opacity-60", toneDot[tone])} />}
      <span className={cn("relative inline-flex size-2.5 rounded-full", toneDot[tone])} />
    </span>
  )
}
