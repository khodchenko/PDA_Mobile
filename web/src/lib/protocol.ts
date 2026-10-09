// Mirrors protocol/snapshot-v1.schema.json. Every game field is optional:
// absent means the game could not read it, not zero.

export const PROTOCOL = 1

export type GameState = "in_game" | "loading" | "dead" | "menu"
export type Reader = "anomaly" | "gamma" | "demo"
export type LinkStatus = "no_data" | "ok" | "stale"

export interface Envelope {
  protocol: number
  seq: number
  seq_end: number
  session: string
}

export interface FastSnapshot extends Envelope {
  kind: "fast"
  game_state?: GameState
  level?: { id: string; name?: string }
  position?: { x: number; y: number; z: number }
  heading_deg?: number
  game_time?: { day: number; hour: number; minute: number }
  health?: number
  radiation?: number
}

export interface Capabilities {
  player?: boolean
  pose?: boolean
  map_texture?: boolean
  tasks?: boolean
  inventory?: boolean
  contacts?: boolean
  messages?: boolean
  relations?: boolean
  encyclopedia?: boolean
  statistics?: boolean
}

export interface PdaTask {
  id: string
  title: string
  description?: string
  storyline?: boolean
}

export interface FactionRelation {
  id: string
  name: string
  goodwill: number
  stance: "ally" | "friend" | "neutral" | "hostile"
}

export interface PdaContact {
  name: string
  community?: string
  rank?: string
}

export interface PdaArticle {
  id: string
  title: string
  category: string
}

export interface PdaMessage {
  channel: string
  sender?: string
  text: string
}

export interface PdaStat {
  id: string
  label: string
  value: number
}

export interface GameMap {
  level: string
  x1: number
  z1: number
  x2: number
  z2: number
  texture: string
  image?: string
}

export interface SlowSnapshot extends Envelope {
  kind: "slow"
  reader?: Reader
  game?: { build?: string; modpack?: string }
  capabilities?: Capabilities
  player?: { name?: string; id?: number; money?: number }
  tasks?: PdaTask[]
  relations?: FactionRelation[]
  contacts?: PdaContact[]
  encyclopedia?: PdaArticle[]
  messages?: PdaMessage[]
  statistics?: PdaStat[]
}

export interface BridgeState {
  protocol: number
  bridge: {
    version: string
    protocol: number
    source: "file" | "demo" | "replay"
    snapshot_dir: string
    uptime_s: number
  }
  link: {
    status: LinkStatus
    fast_age_ms: number | null
    slow_age_ms: number | null
    accepted: { fast: number; slow: number }
    rejected: { fast: number; slow: number }
    last_reject: { fast: string | null; slow: string | null }
  }
  fast: FastSnapshot | null
  slow: SlowSnapshot | null
  map?: GameMap | null
}

export interface Pairing {
  token: string
  urls: string[]
}
