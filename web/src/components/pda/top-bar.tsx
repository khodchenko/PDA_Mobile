import { RadioTower } from "lucide-react"

import { gameClock, gameDay, levelName } from "@/lib/format"
import type { Chain } from "@/lib/link"
import type { FastSnapshot } from "@/lib/protocol"
import { ToneDot } from "./tone"
import { toneText } from "./tone-styles"
import { cn } from "@/lib/utils"

export function TopBar({ chain, fast }: { chain: Chain; fast: FastSnapshot | null }) {
  const { overall } = chain
  return (
    <header className="sticky top-0 z-30 border-b border-border/60 bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-14 max-w-5xl items-center gap-3 px-4">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="grid size-8 shrink-0 place-items-center rounded-md bg-primary/15 text-primary ring-1 ring-primary/30">
            <RadioTower className="size-4" />
          </span>
          <div className="min-w-0 leading-tight">
            <div className="font-mono text-xs tracking-[0.2em] text-muted-foreground uppercase">ПДА</div>
            <div className="truncate text-sm font-medium">{fast?.level ? levelName(fast.level) : "Зона"}</div>
          </div>
        </div>
        <div
          className="ml-auto flex min-w-0 items-center gap-2 rounded-full border border-border/70 bg-card/70 px-3 py-1"
          title={overall.detail}
        >
          <ToneDot tone={overall.tone} pulse={overall.tone === "ok"} />
          <span className={cn("truncate text-xs font-medium", toneText[overall.tone])}>{overall.title}</span>
        </div>
        <div className="hidden text-right leading-tight sm:block">
          <div className="font-mono text-lg tabular-nums">{gameClock(fast?.game_time)}</div>
          <div className="text-[11px] text-muted-foreground">{gameDay(fast?.game_time)}</div>
        </div>
      </div>
    </header>
  )
}
