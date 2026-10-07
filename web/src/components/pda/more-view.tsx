import { Backpack, ListChecks, Mail, Users, type LucideIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { Capabilities, SlowSnapshot } from "@/lib/protocol"

const SECTIONS: { key: keyof Capabilities; icon: LucideIcon; title: string; plan: string }[] = [
  {
    key: "tasks",
    icon: ListChecks,
    title: "Задания",
    plan: "Отдельный читатель для GAMMA: taskboard, динамические задания и FATE. Нужны скрипты из установки 0.9.5.",
  },
  {
    key: "contacts",
    icon: Users,
    title: "Контакты",
    plan: "Группировки, отношения, известные сталкеры и их метки.",
  },
  {
    key: "inventory",
    icon: Backpack,
    title: "Инвентарь",
    plan: "Только чтение: конечности, броня, оружие, патроны, вес, предметы.",
  },
  {
    key: "messages",
    icon: Mail,
    title: "Сообщения",
    plan: "Новости, уведомления и журнал ПДА.",
  },
]

export function MoreView({ slow }: { slow: SlowSnapshot | null }) {
  const caps = slow?.capabilities
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {SECTIONS.map(({ key, icon: Icon, title, plan }) => {
        const on = !!caps?.[key]
        return (
          <Card key={key} className={on ? undefined : "opacity-80"}>
            <CardHeader>
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="flex items-center gap-2">
                  <Icon className="size-4 text-primary" />
                  {title}
                </CardTitle>
                <Badge variant={on ? "default" : "outline"}>{on ? "синхронизируется" : "пока нет"}</Badge>
              </div>
              <CardDescription>
                {on
                  ? "Читатель игры отдаёт этот блок, экран для него появится в следующих срезах."
                  : `Эта сборка не отдаёт ${title.toLowerCase()}.`}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-xs leading-relaxed text-muted-foreground">{plan}</p>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
