import { useCallback, useEffect, useRef, useState } from "react"

import { gameClock, levelName } from "@/lib/format"
import { capabilityList, type ClientStatus, type Stage } from "@/lib/link"
import type { BridgeState, Pairing } from "@/lib/protocol"
import { parseTokenInput, readStoredToken, storeToken, takeTokenFromUrl } from "@/lib/token"

export type LogLevel = "info" | "warn" | "error"

export interface LogEntry {
  id: number
  at: number
  stage: Stage
  level: LogLevel
  text: string
}

export interface Transition {
  id: number
  from: string
  to: string
  gameTime: string
}

export interface Trail {
  levelId: string | null
  points: Array<[number, number]>
}

const LOG_LIMIT = 150
const TRAIL_LIMIT = 600
const TRAIL_MIN_STEP_M = 0.75
// The bridge sends state at least every 5 s, so silence this long means
// the stream died without an error event (common after Android sleeps).
const STREAM_SILENCE_MS = 15_000

const LINK_TEXT = {
  ok: "Игра пишет снимки",
  stale: "Игра перестала писать снимки",
  no_data: "От игры ещё нет снимков",
} as const

function initialToken(): string | null {
  const fromUrl = takeTokenFromUrl()
  if (fromUrl) {
    storeToken(fromUrl)
    return fromUrl
  }
  return readStoredToken()
}

export function useBridge() {
  const [token, setToken] = useState<string | null>(initialToken)
  const [pairing, setPairing] = useState<Pairing | null>(null)
  const [pairingChecked, setPairingChecked] = useState(false)
  const [status, setStatus] = useState<ClientStatus>("starting")
  const [state, setState] = useState<BridgeState | null>(null)
  const [lastMessageAt, setLastMessageAt] = useState<number | null>(null)
  const [reconnects, setReconnects] = useState(0)
  const [log, setLog] = useState<LogEntry[]>([])
  const [trail, setTrail] = useState<Trail>({ levelId: null, points: [] })
  const [transitions, setTransitions] = useState<Transition[]>([])

  const prevRef = useRef<BridgeState | null>(null)
  const idRef = useRef(0)

  const addLog = useCallback((stage: Stage, level: LogLevel, text: string) => {
    const entry = { id: ++idRef.current, at: Date.now(), stage, level, text }
    setLog((items) => [entry, ...items].slice(0, LOG_LIMIT))
  }, [])

  const ingest = useCallback(
    (next: BridgeState) => {
      const prev = prevRef.current
      prevRef.current = next
      setState(next)
      setLastMessageAt(Date.now())

      if (!prev || prev.link.status !== next.link.status) {
        addLog("game", next.link.status === "ok" ? "info" : "warn", LINK_TEXT[next.link.status])
      }
      for (const kind of ["fast", "slow"] as const) {
        if (prev && next.link.rejected[kind] > prev.link.rejected[kind]) {
          addLog("bridge", "warn", `Отклонён ${kind}-снимок: ${next.link.last_reject[kind] ?? "без причины"}`)
        }
      }
      const fast = next.fast
      const prevFast = prev?.fast
      if (fast && prevFast && fast.session !== prevFast.session) {
        addLog("game", "info", "Новая сессия игры: загружено сохранение или начата новая игра")
      }
      if (fast?.game_state && fast.game_state !== prevFast?.game_state) {
        const names = { in_game: "в игре", loading: "загрузка уровня", dead: "персонаж погиб", menu: "главное меню" }
        addLog("game", fast.game_state === "dead" ? "warn" : "info", `Состояние: ${names[fast.game_state]}`)
      }
      const slow = next.slow
      if (slow && (slow.reader !== prev?.slow?.reader || slow.session !== prev?.slow?.session)) {
        const caps = capabilityList(slow.capabilities)
        addLog("adapter", "info", `Читатель ${slow.reader ?? "не указан"}, отдаёт: ${caps.join(", ") || "ничего"}`)
      }

      const levelId = fast?.level?.id
      const prevLevel = prevFast?.level
      if (levelId && prevLevel && prevLevel.id !== levelId && fast?.session === prevFast?.session) {
        const transition = {
          id: ++idRef.current,
          from: levelName(prevLevel),
          to: levelName(fast.level),
          gameTime: gameClock(fast.game_time),
        }
        setTransitions((items) => [transition, ...items].slice(0, 10))
        addLog("game", "info", `Переход: ${transition.from} → ${transition.to}`)
      }

      const pos = fast?.position
      if (levelId && pos) {
        const sessionChanged = !!prevFast && prevFast.session !== fast.session
        setTrail((t) => {
          if (t.levelId !== levelId || sessionChanged) return { levelId, points: [[pos.x, pos.z]] }
          const last = t.points[t.points.length - 1]
          if (last && Math.hypot(last[0] - pos.x, last[1] - pos.z) < TRAIL_MIN_STEP_M) return t
          return { levelId, points: [...t.points, [pos.x, pos.z] as [number, number]].slice(-TRAIL_LIMIT) }
        })
      }
    },
    [addLog],
  )

  useEffect(() => {
    if (pairingChecked) return
    let cancelled = false
    fetch("/api/pairing", { cache: "no-store" })
      .then(async (res) => {
        if (cancelled) return
        if (res.ok) {
          const p = (await res.json()) as Pairing
          if (cancelled) return
          setPairing(p)
          storeToken(p.token)
          setToken(p.token)
        }
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setPairingChecked(true)
      })
    return () => {
      cancelled = true
    }
  }, [pairingChecked])

  useEffect(() => {
    if (!pairingChecked || !token) return
    let cancelled = false
    let es: EventSource | null = null
    let retryTimer: number | undefined
    let failures = 0
    let lastEventAt = 0

    const scheduleRetry = () => {
      const delay = Math.min(10_000, 1000 * 2 ** failures)
      failures += 1
      retryTimer = window.setTimeout(probe, delay)
    }

    const closeStream = () => {
      es?.close()
      es = null
    }

    const onStreamLost = (why: string) => {
      closeStream()
      if (cancelled) return
      setStatus("connecting")
      setReconnects((n) => n + 1)
      addLog("phone", "warn", why)
      scheduleRetry()
    }

    const openStream = () => {
      const source = new EventSource(`/api/stream?token=${encodeURIComponent(token)}`)
      es = source
      lastEventAt = Date.now()
      source.addEventListener("open", () => {
        failures = 0
        setStatus("live")
        addLog("phone", "info", "Поток событий открыт")
      })
      source.addEventListener("state", (ev) => {
        lastEventAt = Date.now()
        try {
          ingest(JSON.parse((ev as MessageEvent<string>).data) as BridgeState)
        } catch {
          addLog("phone", "error", "Событие от моста не разобрано")
        }
      })
      source.addEventListener("error", () => onStreamLost("Поток оборвался, переподключаюсь"))
    }

    async function probe() {
      if (cancelled) return
      setStatus((s) => (s === "bridge_down" ? s : "connecting"))
      let res: Response
      try {
        res = await fetch("/api/state", { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" })
      } catch {
        if (cancelled) return
        setStatus("bridge_down")
        addLog("bridge", "error", "Мост не отвечает по сети")
        scheduleRetry()
        return
      }
      if (cancelled) return
      if (res.status === 401) {
        addLog("phone", "error", "Мост отверг токен: телефон не привязан или токен сброшен")
        storeToken(null)
        setToken(null)
        setPairingChecked(false)
        return
      }
      if (!res.ok) {
        setStatus("bridge_down")
        addLog("bridge", "error", `Мост ответил ошибкой ${res.status}`)
        scheduleRetry()
        return
      }
      try {
        ingest((await res.json()) as BridgeState)
      } catch {
        addLog("bridge", "error", "Ответ моста не разобран")
        scheduleRetry()
        return
      }
      if (!cancelled) openStream()
    }

    const watchdog = window.setInterval(() => {
      if (es && Date.now() - lastEventAt > STREAM_SILENCE_MS) {
        onStreamLost("Мост замолчал больше чем на 15 с, переподключаюсь")
      }
    }, 2000)

    probe()
    return () => {
      cancelled = true
      window.clearTimeout(retryTimer)
      window.clearInterval(watchdog)
      closeStream()
    }
  }, [token, pairingChecked, ingest, addLog])

  const pairWith = useCallback(
    (input: string): boolean => {
      const parsed = parseTokenInput(input)
      if (!parsed) return false
      storeToken(parsed)
      setToken(parsed)
      addLog("phone", "info", "Токен введён вручную")
      return true
    },
    [addLog],
  )

  const forget = useCallback(() => {
    storeToken(null)
    setToken(null)
    setState(null)
    prevRef.current = null
    addLog("phone", "info", "Привязка к мосту удалена на этом устройстве")
  }, [addLog])

  return {
    status: pairingChecked && !token ? ("unpaired" as const) : status,
    state,
    pairing,
    log,
    trail,
    transitions,
    reconnects,
    lastMessageAt,
    pairWith,
    forget,
  }
}

export type Bridge = ReturnType<typeof useBridge>
