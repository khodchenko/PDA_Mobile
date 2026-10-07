import type { FastSnapshot } from "./protocol"

export const DASH = "—"

export function gameClock(t: FastSnapshot["game_time"]): string {
  if (!t) return DASH
  return `${String(t.hour).padStart(2, "0")}:${String(t.minute).padStart(2, "0")}`
}

export function gameDay(t: FastSnapshot["game_time"]): string {
  return t ? `день ${t.day}` : DASH
}

const money = new Intl.NumberFormat("ru-RU")

export function rubles(value: number | undefined): string {
  return value === undefined ? DASH : `${money.format(value)} ₽`
}

export function percent(value: number | undefined): string {
  return value === undefined ? DASH : `${Math.round(value * 100)}%`
}

export function meters(value: number | undefined): string {
  return value === undefined ? DASH : value.toFixed(1)
}

const POINTS = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]

export function compassPoint(deg: number | undefined): string {
  if (deg === undefined) return DASH
  return POINTS[Math.round((((deg % 360) + 360) % 360) / 45) % 8]
}

export function ago(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "ни разу"
  if (ms < 1000) return "только что"
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s} с назад`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m} мин назад`
  return `${Math.floor(m / 60)} ч назад`
}

export function levelName(level: FastSnapshot["level"]): string {
  if (!level) return DASH
  return level.name || level.id
}
