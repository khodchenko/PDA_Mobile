import { Check, Copy, QrCode } from "lucide-react"
import QRCode from "qrcode"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { Pairing } from "@/lib/protocol"

function QrImage({ url }: { url: string }) {
  const [src, setSrc] = useState<string | null>(null)
  useEffect(() => {
    let alive = true
    QRCode.toDataURL(url, { margin: 1, width: 232, color: { dark: "#171a10", light: "#f1edd8" } })
      .then((data) => alive && setSrc(data))
      .catch(() => alive && setSrc(null))
    return () => {
      alive = false
    }
  }, [url])
  return src ? (
    <img src={src} alt="QR-код для привязки телефона" className="size-48 rounded-md" />
  ) : (
    <div className="grid size-48 place-items-center rounded-md bg-muted text-xs text-muted-foreground">QR…</div>
  )
}

function CopyButton({ text }: { text: string }) {
  const [done, setDone] = useState(false)
  return (
    <Button
      size="sm"
      variant="outline"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text)
          setDone(true)
          window.setTimeout(() => setDone(false), 1500)
        } catch {
          setDone(false)
        }
      }}
    >
      {done ? <Check /> : <Copy />}
      {done ? "Скопировано" : "Копировать ссылку"}
    </Button>
  )
}

/** Shown only on the PC itself: the bridge hands the token to loopback only. */
export function PairQr({ pairing }: { pairing: Pairing }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <QrCode className="size-4 text-primary" />
          Подключить телефон
        </CardTitle>
        <CardDescription>
          Телефон должен быть в той же Wi‑Fi сети, что и этот ПК. Наведите камеру на код и откройте ссылку. Чтобы
          ПДА открывался как приложение, в меню браузера выберите «Добавить на главный экран».
        </CardDescription>
      </CardHeader>
      <CardContent>
        {pairing.urls.length === 0 ? (
          <p className="text-sm text-primary">
            Мост не нашёл адрес этого ПК в локальной сети. Подключите ПК к Wi‑Fi или кабелю и перезапустите мост.
          </p>
        ) : (
          <div className="flex flex-wrap gap-6">
            {pairing.urls.map((url) => (
              <div key={url} className="grid justify-items-start gap-2">
                <QrImage url={url} />
                <code className="max-w-56 font-mono text-[11px] break-all text-muted-foreground">
                  {url.replace(/token=.*/, "token=…")}
                </code>
                <CopyButton text={url} />
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
