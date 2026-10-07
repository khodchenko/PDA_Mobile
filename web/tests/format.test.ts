import { describe, expect, it } from "vitest"

import { ago, compassPoint, gameClock, percent, rubles } from "@/lib/format"
import { parseTokenInput } from "@/lib/token"

describe("format", () => {
  it("shows a dash for fields the game did not send", () => {
    expect(rubles(undefined)).toBe("—")
    expect(percent(undefined)).toBe("—")
    expect(gameClock(undefined)).toBe("—")
  })

  it("formats game values", () => {
    expect(gameClock({ day: 2, hour: 7, minute: 5 })).toBe("07:05")
    expect(percent(0.736)).toBe("74%")
    expect(rubles(18450).replace(/\s/g, " ")).toBe("18 450 ₽")
  })

  it("maps headings to compass points", () => {
    expect(compassPoint(0)).toBe("С")
    expect(compassPoint(90)).toBe("В")
    expect(compassPoint(359)).toBe("С")
    expect(compassPoint(-90)).toBe("З")
  })

  it("describes ages", () => {
    expect(ago(null)).toBe("ни разу")
    expect(ago(400)).toBe("только что")
    expect(ago(12_000)).toBe("12 с назад")
  })
})

describe("parseTokenInput", () => {
  it("takes the token from a pasted QR link", () => {
    expect(parseTokenInput(" http://192.168.1.5:47615/?token=abcDEF_123-xyz ")).toBe("abcDEF_123-xyz")
  })

  it("accepts a bare token and rejects junk", () => {
    expect(parseTokenInput("abcDEF_123-xyz")).toBe("abcDEF_123-xyz")
    expect(parseTokenInput("привет")).toBeNull()
    expect(parseTokenInput("")).toBeNull()
  })
})
