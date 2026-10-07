import { Compass, HeartPulse, MapPin, Radiation, User, Wallet } from "lucide-react"
import type { ReactNode } from "react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { compassPoint, DASH, gameClock, gameDay, levelName, meters, percent, rubles } from "@/lib/format"
import type { FastSnapshot, SlowSnapshot } from "@/lib/protocol"
import { cn } from "@/lib/utils"

const MISSING = "Игра не прислала это поле"

function healthColor(v: number) {
  if (v > 0.6) return "*:data-[slot=progress-indicator]:bg-chart-1"
  if (v > 0.3) return "*:data-[slot=progress-indicator]:bg-primary"
  return "*:data-[slot=progress-indicator]:bg-destructive"
}

function Stat({ icon, label, value, missing, children }: {
  icon: ReactNode
  label: string
  value: string
  missing?: boolean
  children?: ReactNode
}) {
  return (
    <div className="rounded-lg border border-border/60 bg-background/40 p-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {icon}
        {label}
      </div>
      <div
        className={cn("mt-1 font-mono text-2xl tabular-nums", missing && "text-muted-foreground/60")}
        title={missing ? MISSING : undefined}
      >
        {value}
      </div>
      {children}
    </div>
  )
}

export function StatusView({ fast, slow }: { fast: FastSnapshot | null; slow: SlowSnapshot | null }) {
  const player = slow?.player
  const pos = fast?.position
  return (
    <div className="grid gap-4 md:grid-cols-5">
      <Card className="md:col-span-3">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <User className="size-3.5" />
                Сталкер
              </div>
              <CardTitle className="mt-1 truncate text-2xl" title={player?.name ? undefined : MISSING}>
                {player?.name ?? DASH}
              </CardTitle>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <span>id {player?.id ?? DASH}</span>
                {slow?.reader === "demo" && <Badge variant="outline">демо</Badge>}
              </div>
            </div>
            <div className="text-right">
              <div className="font-mono text-3xl tabular-nums text-primary">{gameClock(fast?.game_time)}</div>
              <div className="text-xs text-muted-foreground">{gameDay(fast?.game_time)}</div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <Stat
            icon={<HeartPulse className="size-3.5" />}
            label="Здоровье"
            value={percent(fast?.health)}
            missing={fast?.health === undefined}
          >
            <Progress
              value={(fast?.health ?? 0) * 100}
              className={cn("mt-2 h-1.5", healthColor(fast?.health ?? 0))}
              aria-label="Здоровье"
            />
          </Stat>
          <Stat
            icon={<Radiation className="size-3.5" />}
            label="Радиация"
            value={percent(fast?.radiation)}
            missing={fast?.radiation === undefined}
          >
            <Progress
              value={(fast?.radiation ?? 0) * 100}
              className="mt-2 h-1.5 *:data-[slot=progress-indicator]:bg-chart-2"
              aria-label="Радиация"
            />
          </Stat>
          <Stat
            icon={<Wallet className="size-3.5" />}
            label="Деньги"
            value={rubles(player?.money)}
            missing={player?.money === undefined}
          />
          <Stat
            icon={<MapPin className="size-3.5" />}
            label="Локация"
            value={levelName(fast?.level)}
            missing={!fast?.level}
          >
            <div className="mt-1 truncate font-mono text-[11px] text-muted-foreground">{fast?.level?.id ?? ""}</div>
          </Stat>
        </CardContent>
      </Card>

      <Card className="md:col-span-2">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Compass className="size-4 text-primary" />
            Положение
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          <div className="grid grid-cols-3 gap-2 font-mono tabular-nums">
            {(["x", "y", "z"] as const).map((axis) => (
              <div key={axis} className="rounded-md border border-border/60 bg-background/40 px-2.5 py-2">
                <div className="text-[11px] text-muted-foreground uppercase">{axis}</div>
                <div className={cn("text-base", !pos && "text-muted-foreground/60")}>{meters(pos?.[axis])}</div>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between rounded-md border border-border/60 bg-background/40 px-3 py-2">
            <span className="text-xs text-muted-foreground">Направление взгляда</span>
            <span className="font-mono tabular-nums">
              {fast?.heading_deg === undefined ? DASH : `${Math.round(fast.heading_deg)}° ${compassPoint(fast.heading_deg)}`}
            </span>
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            Координаты мира X-Ray в метрах: x на восток, z на север, y высота.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
