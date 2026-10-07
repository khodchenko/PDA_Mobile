import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

import { describeChain, liveAge, type ClientInfo } from "@/lib/link"
import type { BridgeState, FastSnapshot, SlowSnapshot } from "@/lib/protocol"

const fixture = <T>(name: string): T =>
  JSON.parse(readFileSync(resolve(import.meta.dirname, "../../protocol/fixtures", name), "utf-8")) as T

const live: ClientInfo = { status: "live", reconnects: 0, sinceMessageMs: 200 }

function bridgeState(overrides: Partial<BridgeState> = {}): BridgeState {
  return {
    protocol: 1,
    bridge: { version: "0.1.0", protocol: 1, source: "file", snapshot_dir: "C:/pda", uptime_s: 30 },
    link: {
      status: "ok",
      fast_age_ms: 80,
      slow_age_ms: 600,
      accepted: { fast: 10, slow: 2 },
      rejected: { fast: 0, slow: 0 },
      last_reject: { fast: null, slow: null },
    },
    fast: fixture<FastSnapshot>("fast-in-game.json"),
    slow: fixture<SlowSnapshot>("slow-partial.json"),
    ...overrides,
  }
}

describe("describeChain", () => {
  it("is green when every link works and data comes from the game", () => {
    const chain = describeChain(live, bridgeState())
    expect(chain.overall).toMatchObject({ tone: "ok", title: "На связи" })
    expect(chain.steps.map((s) => s.tone)).toEqual(["ok", "ok", "ok", "ok"])
    expect(chain.steps[1].title).toBe("GAMMA: GAMMA, Anomaly 1.5.3")
  })

  it("labels demo data so nobody mistakes it for the game", () => {
    const chain = describeChain(live, bridgeState({ slow: fixture<SlowSnapshot>("slow-demo.json") }))
    expect(chain.overall.title).toBe("Демо-режим")
  })

  it("blames the phone when it is not paired", () => {
    const chain = describeChain({ ...live, status: "unpaired" }, null)
    expect(chain.overall).toMatchObject({ stage: "phone", tone: "bad" })
  })

  it("blames the bridge when it does not answer", () => {
    const chain = describeChain({ ...live, status: "bridge_down" }, null)
    expect(chain.overall.stage).toBe("bridge")
    expect(chain.steps.find((s) => s.stage === "bridge")?.tone).toBe("bad")
  })

  it("says the game is silent when snapshots go stale", () => {
    const state = bridgeState()
    state.link = { ...state.link, status: "stale", fast_age_ms: 9000 }
    const chain = describeChain(live, state)
    expect(chain.overall).toMatchObject({ stage: "game", tone: "warn", title: "Игра молчит" })
    expect(chain.steps[0].detail).toContain("пауза")
  })

  it("points at broken files when nothing was ever accepted", () => {
    const state = bridgeState({ fast: null, slow: null })
    state.link = {
      ...state.link,
      status: "no_data",
      fast_age_ms: null,
      rejected: { fast: 3, slow: 0 },
      last_reject: { fast: "seq 4 не совпадает с seq_end 3", slow: null },
    }
    const chain = describeChain(live, state)
    expect(chain.overall).toMatchObject({ stage: "game", tone: "bad" })
    expect(chain.overall.detail).toContain("seq_end")
  })

  it("waits for the game when the bridge has no files yet", () => {
    const state = bridgeState({ fast: null, slow: null })
    state.link = { ...state.link, status: "no_data", fast_age_ms: null }
    expect(describeChain(live, state).overall.title).toBe("Ждём игру")
  })

  it("reports loading and death from the fast snapshot", () => {
    expect(describeChain(live, bridgeState({ fast: fixture("fast-loading.json") })).overall.title).toBe(
      "Загрузка уровня",
    )
    const dead = { ...fixture<FastSnapshot>("fast-in-game.json"), game_state: "dead" as const }
    expect(describeChain(live, bridgeState({ fast: dead })).overall).toMatchObject({ tone: "bad" })
  })

  it("refuses a bridge speaking another protocol", () => {
    const chain = describeChain(live, bridgeState({ protocol: 2 }))
    expect(chain.overall).toMatchObject({ stage: "bridge", tone: "bad" })
  })

  it("warns when the reader exposes no data blocks", () => {
    const slow = { ...fixture<SlowSnapshot>("slow-partial.json"), capabilities: {} }
    expect(describeChain(live, bridgeState({ slow })).steps[1].tone).toBe("warn")
  })
})

describe("liveAge", () => {
  it("adds time spent on the device", () => {
    expect(liveAge(500, 1500)).toBe(2000)
    expect(liveAge(null, 1500)).toBeNull()
  })
})
