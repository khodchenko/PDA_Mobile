import { Link2, RadioTower } from "lucide-react"
import { useState, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"

export function PairScreen({ onPair }: { onPair: (input: string) => boolean }) {
  const [value, setValue] = useState("")
  const [error, setError] = useState<string | null>(null)
  const pcUrl = `http://localhost:${window.location.port || "47615"}`

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setError(onPair(value) ? null : "Не похоже на ссылку из QR-кода или токен. Скопируйте ссылку целиком.")
  }

  return (
    <main className="mx-auto grid min-h-dvh max-w-md place-items-center px-4 py-10">
      <Card className="w-full">
        <CardHeader>
          <span className="mb-2 grid size-10 place-items-center rounded-lg bg-primary/15 text-primary ring-1 ring-primary/30">
            <RadioTower className="size-5" />
          </span>
          <CardTitle className="text-xl">Привяжите телефон к мосту</CardTitle>
          <CardDescription>
            Мост на ПК отвечает, но отдаёт данные игры только привязанным устройствам.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-5">
          <ol className="grid gap-2 text-sm">
            <li>
              <span className="text-primary">1.</span> На ПК откройте{" "}
              <code className="rounded bg-muted px-1 font-mono text-xs">{pcUrl}</code>
            </li>
            <li>
              <span className="text-primary">2.</span> Перейдите во вкладку «Связь».
            </li>
            <li>
              <span className="text-primary">3.</span> Отсканируйте QR-код камерой этого телефона.
            </li>
          </ol>
          <form onSubmit={submit} className="grid gap-2">
            <label htmlFor="pair-input" className="text-xs text-muted-foreground">
              Или вставьте ссылку из QR-кода
            </label>
            <div className="flex gap-2">
              <Input
                id="pair-input"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="http://192.168.…/?token=…"
                autoComplete="off"
                autoCapitalize="off"
                spellCheck={false}
              />
              <Button type="submit" disabled={!value.trim()}>
                <Link2 />
                Привязать
              </Button>
            </div>
            {error && <p className="text-xs text-destructive">{error}</p>}
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
