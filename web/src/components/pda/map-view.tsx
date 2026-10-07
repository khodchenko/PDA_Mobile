import { ArrowRightLeft, Minus, Navigation, Plus } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { Trail, Transition } from "@/hooks/use-bridge"
import { compassPoint, DASH, levelName, meters } from "@/lib/format"
import type { FastSnapshot, SlowSnapshot } from "@/lib/protocol"

const RADII = [25, 50, 100, 250, 500]

function gridStep(radius: number): number {
  const raw = radius / 4
  for (const step of [5, 10, 25, 50, 100, 250]) if (step >= raw) return step
  return 500
}

export function MapView({ fast, slow, trail, transitions }: {
  fast: FastSnapshot | null
  slow: SlowSnapshot | null
  trail: Trail
  transitions: Transition[]
}) {
  const [zoom, setZoom] = useState(2)
  const radius = RADII[zoom]
  const pos = fast?.position
  const heading = fast?.heading_deg
  const step = gridStep(radius)

  // Map space: north up, so screen y is -z. Centered on the player.
  const cx = pos?.x ?? 0
  const cz = pos?.z ?? 0
  const toScreen = (x: number, z: number) => `${(x - cx).toFixed(2)},${(-(z - cz)).toFixed(2)}`

  const lines: { key: string; x1: number; y1: number; x2: number; y2: number; major: boolean }[] = []
  for (let gx = Math.floor((cx - radius) / step) * step; gx <= cx + radius; gx += step) {
    lines.push({ key: `x${gx}`, x1: gx - cx, y1: -radius, x2: gx - cx, y2: radius, major: gx % (step * 4) === 0 })
  }
  for (let gz = Math.floor((cz - radius) / step) * step; gz <= cz + radius; gz += step) {
    lines.push({ key: `z${gz}`, x1: -radius, y1: -(gz - cz), x2: radius, y2: -(gz - cz), major: gz % (step * 4) === 0 })
  }
  const showTrail = pos && trail.levelId === fast?.level?.id && trail.points.length > 1
  const arrow = radius * 0.07

  return (
    <div className="grid gap-4 md:grid-cols-[1fr_18rem]">
      <Card className="gap-3 py-3">
        <CardHeader className="px-3">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="truncate">{levelName(fast?.level)}</CardTitle>
            <div className="flex items-center gap-1">
              <Button
                size="icon"
                variant="outline"
                onClick={() => setZoom((z) => Math.min(RADII.length - 1, z + 1))}
                disabled={zoom === RADII.length - 1}
                aria-label="Отдалить"
              >
                <Minus />
              </Button>
              <span className="w-16 text-center font-mono text-xs tabular-nums text-muted-foreground">±{radius} м</span>
              <Button
                size="icon"
                variant="outline"
                onClick={() => setZoom((z) => Math.max(0, z - 1))}
                disabled={zoom === 0}
                aria-label="Приблизить"
              >
                <Plus />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="px-3">
          <div className="relative mx-auto aspect-square w-full max-w-[min(100%,68dvh)] overflow-hidden rounded-lg border border-border/70 bg-[radial-gradient(circle_at_center,oklch(0.26_0.03_120),oklch(0.17_0.012_115))]">
            <svg
              viewBox={`${-radius} ${-radius} ${radius * 2} ${radius * 2}`}
              className="absolute inset-0 size-full"
              role="img"
              aria-label="Положение игрока на сетке локации"
            >
              {lines.map(({ key, major, ...l }) => (
                <line
                  key={key}
                  {...l}
                  stroke="currentColor"
                  className={major ? "text-foreground/20" : "text-foreground/[0.07]"}
                  strokeWidth={major ? 1.2 : 1}
                  vectorEffect="non-scaling-stroke"
                />
              ))}
              <circle
                r={radius / 2}
                fill="none"
                stroke="currentColor"
                className="text-primary/25"
                strokeDasharray="4 6"
                vectorEffect="non-scaling-stroke"
              />
              {showTrail && (
                <polyline
                  points={trail.points.map(([x, z]) => toScreen(x, z)).join(" ")}
                  fill="none"
                  stroke="currentColor"
                  className="text-primary/60"
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  vectorEffect="non-scaling-stroke"
                />
              )}
              {pos && (
                <g transform={`rotate(${heading ?? 0})`}>
                  {heading !== undefined && (
                    <path
                      d={`M0 0 L${-arrow * 2.2} ${-arrow * 5} A${arrow * 5.5} ${arrow * 5.5} 0 0 1 ${arrow * 2.2} ${-arrow * 5} Z`}
                      className="fill-primary/15"
                    />
                  )}
                  <path
                    d={`M0 ${-arrow * 1.4} L${arrow} ${arrow} L0 ${arrow * 0.45} L${-arrow} ${arrow} Z`}
                    className="fill-primary stroke-background"
                    strokeWidth={1.5}
                    vectorEffect="non-scaling-stroke"
                  />
                </g>
              )}
            </svg>
            <div className="pointer-events-none absolute top-2 left-2 flex items-center gap-1 rounded bg-background/70 px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">
              <Navigation className="size-3 fill-current" />С
            </div>
            <div className="pointer-events-none absolute bottom-2 left-2 rounded bg-background/70 px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground">
              клетка {step} м · кольцо {radius / 2} м
            </div>
            {!pos && (
              <div className="absolute inset-0 grid place-items-center p-6 text-center">
                <div className="max-w-xs rounded-lg bg-background/80 px-4 py-3 text-sm text-muted-foreground">
                  {fast?.game_state === "loading"
                    ? "Загрузка уровня. Позиция появится, когда игрок окажется на локации."
                    : "Игра не прислала позицию игрока."}
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid content-start gap-4">
        <Card size="sm">
          <CardHeader>
            <CardTitle>Игрок</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-1.5 font-mono text-sm tabular-nums">
            <Row label="x · восток" value={meters(pos?.x)} />
            <Row label="z · север" value={meters(pos?.z)} />
            <Row label="y · высота" value={meters(pos?.y)} />
            <Row
              label="взгляд"
              value={heading === undefined ? DASH : `${Math.round(heading)}° ${compassPoint(heading)}`}
            />
          </CardContent>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ArrowRightLeft className="size-4 text-primary" />
              Переходы
            </CardTitle>
          </CardHeader>
          <CardContent>
            {transitions.length === 0 ? (
              <p className="text-xs text-muted-foreground">С момента подключения игрок не менял локацию.</p>
            ) : (
              <ul className="grid gap-1.5 text-sm">
                {transitions.slice(0, 5).map((t) => (
                  <li key={t.id} className="flex items-baseline justify-between gap-2">
                    <span className="truncate">
                      {t.from} → <span className="text-primary">{t.to}</span>
                    </span>
                    <span className="shrink-0 font-mono text-xs text-muted-foreground">{t.gameTime}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
        {!slow?.capabilities?.map_texture && (
          <p className="px-1 text-xs leading-relaxed text-muted-foreground">
            Подложки карты пока нет: текстуры локаций ещё не импортированы из установки игры. Сетка в метрах, север
            сверху, след показывает путь с момента подключения.
          </p>
        )}
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="font-sans text-xs text-muted-foreground">{label}</span>
      <span>{value}</span>
    </div>
  )
}
