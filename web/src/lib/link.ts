import { ago } from "./format"
import { PROTOCOL, type BridgeState, type Capabilities } from "./protocol"

export type ClientStatus = "starting" | "unpaired" | "bridge_down" | "connecting" | "live"
export type Tone = "ok" | "warn" | "bad" | "idle"
export type Stage = "game" | "adapter" | "bridge" | "phone"

export interface ClientInfo {
  status: ClientStatus
  reconnects: number
  // Milliseconds since the last state event reached this device.
  sinceMessageMs: number | null
}

export interface Verdict {
  tone: Tone
  title: string
  detail: string
}

export interface ChainStep extends Verdict {
  stage: Stage
  label: string
}

export interface Chain {
  overall: Verdict & { stage: Stage | null }
  steps: ChainStep[]
}

const CAPABILITY_LABELS: Record<keyof Capabilities, string> = {
  player: "игрок",
  pose: "позиция",
  map_texture: "подложка карты",
  tasks: "задания",
  inventory: "инвентарь",
  contacts: "контакты",
  messages: "сообщения",
  relations: "группировки",
  encyclopedia: "справочник",
  statistics: "статистика",
}

export function capabilityList(caps: Capabilities | undefined): string[] {
  if (!caps) return []
  return (Object.keys(CAPABILITY_LABELS) as (keyof Capabilities)[])
    .filter((k) => caps[k])
    .map((k) => CAPABILITY_LABELS[k])
}

// Ages from the bridge were measured when it sent the event, so add the
// time the event has been sitting on this device.
export function liveAge(ms: number | null | undefined, sinceMessageMs: number | null): number | null {
  if (ms === null || ms === undefined) return null
  return ms + (sinceMessageMs ?? 0)
}

function phoneStep(client: ClientInfo): ChainStep {
  const base = { stage: "phone" as const, label: "Телефон" }
  switch (client.status) {
    case "live":
      return {
        ...base,
        tone: "ok",
        title: "Поток открыт",
        detail:
          client.reconnects > 0
            ? `Переподключений: ${client.reconnects}. Последнее событие ${ago(client.sinceMessageMs)}.`
            : `Последнее событие ${ago(client.sinceMessageMs)}.`,
      }
    case "unpaired":
      return { ...base, tone: "bad", title: "Не привязан", detail: "Нужен QR-код или токен с ПК." }
    case "bridge_down":
      return { ...base, tone: "bad", title: "Нет ответа от моста", detail: "Повторяю попытку." }
    default:
      return { ...base, tone: "idle", title: "Подключаюсь", detail: "Жду первое событие от моста." }
  }
}

function bridgeStep(client: ClientInfo, state: BridgeState | null): ChainStep {
  const base = { stage: "bridge" as const, label: "Мост на ПК" }
  if (client.status === "bridge_down") {
    return {
      ...base,
      tone: "bad",
      title: "Не отвечает",
      detail: "Мост не запущен, ПК в другой сети или порт закрыт брандмауэром.",
    }
  }
  if (!state) return { ...base, tone: "idle", title: "Нет данных", detail: "Состояние ещё не получено." }
  if (state.protocol !== PROTOCOL) {
    return {
      ...base,
      tone: "bad",
      title: `Протокол ${state.protocol}`,
      detail: `Экран понимает протокол ${PROTOCOL}. Обновите мост или экран.`,
    }
  }
  const source = { file: "файлы игры", demo: "демо без игры", replay: "запись" }[state.bridge.source]
  return {
    ...base,
    tone: "ok",
    title: `Работает, ${state.bridge.version}`,
    detail: `Источник: ${source}. Папка: ${state.bridge.snapshot_dir}`,
  }
}

function gameStep(state: BridgeState | null, sinceMessageMs: number | null): ChainStep {
  const base = { stage: "game" as const, label: "Игра" }
  if (!state) return { ...base, tone: "idle", title: "Неизвестно", detail: "Мост пока ничего не сообщил." }
  const { link } = state
  const rejected = link.rejected.fast + link.rejected.slow
  const rejectNote = rejected > 0 ? ` Отклонено битых снимков: ${rejected}.` : ""
  if (link.status === "no_data") {
    const lastReject = link.last_reject.fast ?? link.last_reject.slow
    return {
      ...base,
      tone: lastReject ? "bad" : "warn",
      title: lastReject ? "Снимки битые" : "Снимков нет",
      detail: lastReject
        ? `Файлы есть, но ни один не принят: ${lastReject}`
        : "Игра с аддоном ещё не записала ни одного снимка в папку моста.",
    }
  }
  const age = liveAge(link.fast_age_ms, sinceMessageMs)
  if (link.status === "stale") {
    return {
      ...base,
      tone: "warn",
      title: "Молчит",
      detail: `Последний снимок ${ago(age)}. Обычно это главное меню, пауза или закрытая игра.${rejectNote}`,
    }
  }
  return { ...base, tone: "ok", title: "Пишет снимки", detail: `Последний снимок ${ago(age)}.${rejectNote}` }
}

function adapterStep(state: BridgeState | null): ChainStep {
  const base = { stage: "adapter" as const, label: "Адаптер" }
  const slow = state?.slow
  if (!slow) {
    return { ...base, tone: "idle", title: "Нет описания", detail: "Медленный снимок ещё не пришёл." }
  }
  if (!slow.reader) {
    return { ...base, tone: "warn", title: "Без имени", detail: "Снимок не сообщил, какой читатель его собрал." }
  }
  const caps = capabilityList(slow.capabilities)
  const name = { anomaly: "Anomaly", gamma: "GAMMA", demo: "Демо" }[slow.reader]
  const build = [slow.game?.modpack, slow.game?.build].filter(Boolean).join(", ")
  return {
    ...base,
    tone: caps.length ? "ok" : "warn",
    title: build ? `${name}: ${build}` : name,
    detail: caps.length ? `Отдаёт: ${caps.join(", ")}.` : "Не отдаёт ни одного блока данных.",
  }
}

export function describeChain(client: ClientInfo, state: BridgeState | null): Chain {
  const steps = [
    gameStep(state, client.sinceMessageMs),
    adapterStep(state),
    bridgeStep(client, state),
    phoneStep(client),
  ]
  return { overall: overallVerdict(client, state, steps), steps }
}

function overallVerdict(client: ClientInfo, state: BridgeState | null, steps: ChainStep[]): Chain["overall"] {
  if (client.status === "unpaired") {
    return { stage: "phone", tone: "bad", title: "Телефон не привязан", detail: "Отсканируйте QR-код на ПК во вкладке «Связь»." }
  }
  if (client.status === "bridge_down") {
    return {
      stage: "bridge",
      tone: "bad",
      title: "Мост не отвечает",
      detail: "Проверьте, что мост запущен на ПК и телефон в той же сети.",
    }
  }
  if (!state) return { stage: null, tone: "idle", title: "Подключение…", detail: "Жду ответ моста." }

  const broken = steps.find((s) => s.tone === "bad")
  if (broken) return { stage: broken.stage, tone: "bad", title: `${broken.label}: ${broken.title}`, detail: broken.detail }

  if (state.link.status === "no_data") {
    return {
      stage: "game",
      tone: "warn",
      title: "Ждём игру",
      detail: "Мост работает. Запустите игру с аддоном и загрузите сохранение.",
    }
  }
  if (state.link.status === "stale") {
    return { stage: "game", tone: "warn", title: "Игра молчит", detail: steps[0].detail }
  }
  switch (state.fast?.game_state) {
    case "loading":
      return { stage: "game", tone: "idle", title: "Загрузка уровня", detail: "Позиция появится после загрузки." }
    case "dead":
      return { stage: "game", tone: "bad", title: "Персонаж погиб", detail: "Данные обновятся после загрузки сохранения." }
    case "menu":
      return { stage: "game", tone: "warn", title: "Главное меню", detail: "Загрузите сохранение." }
  }
  if (state.slow?.reader === "demo") {
    return { stage: null, tone: "ok", title: "Демо-режим", detail: "Данные имитирует мост. Игра не подключена." }
  }
  return { stage: null, tone: "ok", title: "На связи", detail: "Данные идут из игры." }
}
