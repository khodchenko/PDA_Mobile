import { spawnSync } from "node:child_process"
import { mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, resolve } from "node:path"
import { Ajv2020 } from "ajv/dist/2020.js"
import { afterAll, describe, expect, it } from "vitest"

const root = resolve(import.meta.dirname, "../..")
const schema = JSON.parse(readFileSync(resolve(root, "protocol/snapshot-v1.schema.json"), "utf-8"))
const validate = new Ajv2020({ allErrors: true, strict: false }).compile(schema)
const hasLuajit = spawnSync("luajit", ["-v"]).status === 0
const dirs: string[] = []

function runScenario(scenario: string) {
  const out = mkdtempSync(join(tmpdir(), "xpda-"))
  dirs.push(out)
  mkdirSync(join(out, "appdata"))
  mkdirSync(join(out, "saves"))
  const gamedata = resolve(root, "addon/stalker_pda/gamedata")
  const proc = spawnSync(
    "luajit",
    [resolve(root, "addon/tests/harness.lua"), join(gamedata, "scripts"), join(gamedata, "configs"), out, scenario],
    { encoding: "utf-8" },
  )
  expect(proc.stderr).toBe("")
  expect(proc.status).toBe(0)
  const lines = (name: string) =>
    readFileSync(join(out, name), "utf-8")
      .split("\n")
      .filter(Boolean)
      .map((l) => JSON.parse(l))
  return [...lines("fast.jsonl"), ...lines("slow.jsonl")]
}

afterAll(() => dirs.forEach((d) => rmSync(d, { recursive: true, force: true })))

describe.skipIf(!hasLuajit)("Lua exporter output", () => {
  it.each(["normal", "broken_api", "utf8_names", "bad_time"])("fits the schema in scenario %s", (scenario) => {
    const docs = runScenario(scenario)
    expect(docs.length).toBeGreaterThan(5)
    for (const doc of docs) {
      validate(doc)
      expect(validate.errors ?? [], JSON.stringify(doc)).toEqual([])
    }
  })
})
