import { Activity, Unlink } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import type { LogEntry } from "@/hooks/use-bridge"
import type { Chain, Stage } from "@/lib/link"
import type { BridgeState, Pairing } from "@/lib/protocol"
import { cn } from "@/lib/utils"
import { PairQr } from "./pair-qr"
import { ToneDot } from "./tone"
import { toneText } from "./tone-styles"

const STAGE_LABEL: Record<Stage, string> = { game: "игра", adapter: "адаптер", bridge: "мост", phone: "телефон" }

const time = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit", second: "2-digit" })

function uptime(s: number) {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h ? `${h} ч ${m} мин` : `${m} мин ${s % 60} с`
}

export function LinkView({ chain, state, pairing, log, onForget }: {
  chain: Chain
  state: BridgeState | null
  pairing: Pairing | null
  log: LogEntry[]
  onForget: () => void
}) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="size-4 text-primary" />
            Цепочка связи
          </CardTitle>
          <CardDescription>Первое красное звено и есть место обрыва.</CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="relative grid gap-4">
            {chain.steps.map((step, i) => (
              <li key={step.stage} className="relative grid grid-cols-[auto_1fr] gap-x-3">
                <div className="flex flex-col items-center pt-1">
                  <ToneDot tone={step.tone} />
                  {i < chain.steps.length - 1 && <span className="mt-1 w-px flex-1 bg-border" />}
                </div>
                <div className="min-w-0 pb-1">
                  <div className="flex flex-wrap items-baseline gap-x-2">
                    <span className="text-xs tracking-wide text-muted-foreground uppercase">{step.label}</span>
                    <span className={cn("text-sm font-medium", toneText[step.tone])}>{step.title}</span>
                  </div>
                  <p className="mt-0.5 text-xs leading-relaxed break-words text-muted-foreground">{step.detail}</p>
                </div>
              </li>
            ))}
          </ol>
          {state && (
            <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-1.5 border-t border-border/60 pt-4 text-xs">
              <dt className="text-muted-foreground">Мост работает</dt>
              <dd className="text-right font-mono">{uptime(state.bridge.uptime_s)}</dd>
              <dt className="text-muted-foreground">Принято снимков</dt>
              <dd className="text-right font-mono">
                {state.link.accepted.fast} / {state.link.accepted.slow}
              </dd>
              <dt className="text-muted-foreground">Отклонено битых</dt>
              <dd className="text-right font-mono">
                {state.link.rejected.fast} / {state.link.rejected.slow}
              </dd>
            </dl>
          )}
          {!pairing && (
            <Button variant="outline" size="sm" className="mt-5" onClick={onForget}>
              <Unlink />
              Отвязать это устройство
            </Button>
          )}
        </CardContent>
      </Card>

      <div className="grid content-start gap-4">
        {pairing && <PairQr pairing={pairing} />}
        <Card>
          <CardHeader>
            <CardTitle>Журнал</CardTitle>
            <CardDescription>События этого экрана, новые сверху. Полный лог моста: bridge/.data/bridge.log.</CardDescription>
          </CardHeader>
          <CardContent>
            {log.length === 0 ? (
              <p className="text-xs text-muted-foreground">Пока пусто.</p>
            ) : (
              <ScrollArea className="h-72 pr-3">
                <ul className="grid gap-2">
                  {log.map((e) => (
                    <li key={e.id} className="grid grid-cols-[auto_auto_1fr] items-baseline gap-2 text-xs">
                      <span className="font-mono text-muted-foreground tabular-nums">{time.format(e.at)}</span>
                      <Badge variant="outline" className="h-4 px-1.5 text-[10px]">
                        {STAGE_LABEL[e.stage]}
                      </Badge>
                      <span
                        className={cn(
                          "break-words",
                          e.level === "error" && "text-destructive",
                          e.level === "warn" && "text-primary",
                        )}
                      >
                        {e.text}
                      </span>
                    </li>
                  ))}
                </ul>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
