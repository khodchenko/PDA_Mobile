import type { Tone } from "@/lib/link"

export const toneText: Record<Tone, string> = {
  ok: "text-chart-1",
  warn: "text-primary",
  bad: "text-destructive",
  idle: "text-muted-foreground",
}
