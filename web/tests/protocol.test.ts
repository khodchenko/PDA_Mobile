import { readFileSync, readdirSync } from "node:fs"
import { resolve } from "node:path"
import { Ajv2020 } from "ajv/dist/2020.js"
import { describe, expect, it } from "vitest"

const protocolDir = resolve(import.meta.dirname, "../../protocol")
const schema = JSON.parse(readFileSync(resolve(protocolDir, "snapshot-v1.schema.json"), "utf-8"))
const validate = new Ajv2020({ allErrors: true, strict: false }).compile(schema)

const load = (name: string) => JSON.parse(readFileSync(resolve(protocolDir, "fixtures", name), "utf-8"))

describe("snapshot schema", () => {
  const fixtures = readdirSync(resolve(protocolDir, "fixtures")).filter((f) => f.endsWith(".json"))

  it.each(fixtures)("accepts fixture %s", (name) => {
    const ok = validate(load(name))
    expect(validate.errors ?? []).toEqual([])
    expect(ok).toBe(true)
  })

  it("rejects health above 1", () => {
    expect(validate({ ...load("fast-in-game.json"), health: 1.5 })).toBe(false)
  })

  it("rejects unknown fields so typos in the Lua writer surface", () => {
    expect(validate({ ...load("fast-in-game.json"), helth: 0.5 })).toBe(false)
  })

  it("rejects a snapshot without seq_end", () => {
    const doc = load("slow-demo.json")
    delete doc.seq_end
    expect(validate(doc)).toBe(false)
  })
})
