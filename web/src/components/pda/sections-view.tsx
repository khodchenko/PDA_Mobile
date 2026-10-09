import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { PdaArticle, PdaContact, PdaMessage, PdaStat, PdaTask, FactionRelation } from "@/lib/protocol"

const STANCE: Record<FactionRelation["stance"], { label: string; className: string }> = {
  ally: { label: "союз", className: "text-emerald-400" },
  friend: { label: "дружелюбие", className: "text-lime-300" },
  neutral: { label: "нейтрально", className: "text-amber-300" },
  hostile: { label: "вражда", className: "text-red-400" },
}

const FACTION_NAMES: Record<string, string> = {
  stalker: "Одиночки",
  dolg: "Долг",
  freedom: "Свобода",
  csky: "Чистое небо",
  ecolog: "Экологи",
  killer: "Наёмники",
  army: "Военные",
  bandit: "Бандиты",
  monolith: "Монолит",
}

function factionName(row: FactionRelation): string {
  if (row.name !== row.id) return row.name
  return FACTION_NAMES[row.id] ?? row.name
}

function Empty({ text }: { text: string }) {
  return <p className="text-sm leading-relaxed text-muted-foreground">{text}</p>
}

export function TasksView({ tasks, available }: { tasks: PdaTask[] | undefined; available: boolean }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Активные задания</CardTitle>
        <CardDescription>То, что ещё не закрыто и не провалено.</CardDescription>
      </CardHeader>
      <CardContent>
        {!available ? (
          <Empty text="Игра ещё не отдала список заданий. Перезапусти сохранение, если аддон только что обновился." />
        ) : tasks && tasks.length > 0 ? (
          <ul className="grid gap-3">
            {tasks.map((task) => (
              <li key={task.id} className="rounded-lg border border-border/70 px-3 py-2">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-medium">{task.title}</span>
                  {task.storyline && <span className="shrink-0 text-xs text-primary">сюжет</span>}
                </div>
                {task.description && <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{task.description}</p>}
              </li>
            ))}
          </ul>
        ) : (
          <Empty text="Сейчас нет активных заданий." />
        )}
      </CardContent>
    </Card>
  )
}

export function RelationsView({ rows, available }: { rows: FactionRelation[] | undefined; available: boolean }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Отношения группировок</CardTitle>
        <CardDescription>Как группировки относятся к тебе. Число — репутация из игры.</CardDescription>
      </CardHeader>
      <CardContent>
        {!available ? (
          <Empty text="Реестр отношений в этой сессии недоступен." />
        ) : (
          <ul className="grid gap-2">
            {(rows ?? []).map((row) => {
              const stance = STANCE[row.stance]
              return (
                <li key={row.id} className="flex items-baseline justify-between gap-3 text-sm">
                  <span>{factionName(row)}</span>
                  <span className="font-mono tabular-nums">
                    <span className={stance.className}>{stance.label}</span>
                    <span className="ml-2 text-muted-foreground">{row.goodwill}</span>
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

export function ContactsView({ rows, available }: { rows: PdaContact[] | undefined; available: boolean }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Контакты</CardTitle>
        <CardDescription>Живые сталкеры в радиусе ПДА, около 80 метров, кроме врагов.</CardDescription>
      </CardHeader>
      <CardContent>
        {!available ? (
          <Empty text="Список контактов игра ещё не отдала." />
        ) : rows && rows.length > 0 ? (
          <ul className="grid gap-2">
            {rows.map((row, index) => (
              <li key={`${row.name}-${index}`} className="flex items-baseline justify-between gap-3 text-sm">
                <span className="truncate font-medium">{row.name}</span>
                <span className="shrink-0 text-right text-muted-foreground">
                  {[row.community, row.rank].filter(Boolean).join(" · ")}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <Empty text="Рядом никого нет." />
        )}
      </CardContent>
    </Card>
  )
}

export function EncyclopediaView({ rows, available }: { rows: PdaArticle[] | undefined; available: boolean }) {
  const groups = new Map<string, PdaArticle[]>()
  for (const row of rows ?? []) {
    const list = groups.get(row.category) ?? []
    list.push(row)
    groups.set(row.category, list)
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Справочник</CardTitle>
        <CardDescription>Открытые статьи. Закрытые в список не попадают.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        {!available ? (
          <Empty text="Справочник в этой сессии недоступен." />
        ) : groups.size === 0 ? (
          <Empty text="Пока нет открытых статей." />
        ) : (
          [...groups.entries()].map(([category, articles]) => (
            <section key={category}>
              <h3 className="mb-1 text-xs tracking-wide text-muted-foreground uppercase">{category}</h3>
              <ul className="grid gap-1 text-sm">
                {articles.map((article) => (
                  <li key={article.id}>{article.title}</li>
                ))}
              </ul>
            </section>
          ))
        )}
      </CardContent>
    </Card>
  )
}

export function MessagesView({ rows, available }: { rows: PdaMessage[] | undefined; available: boolean }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Сообщения</CardTitle>
        <CardDescription>Живая очередь радионовостей. Старый журнал ПДА движок скриптам не отдаёт.</CardDescription>
      </CardHeader>
      <CardContent>
        {!available ? (
          <Empty text="Очередь новостей в этой сессии недоступна. Сохранённый журнал ПДА из движка прочитать нельзя." />
        ) : rows && rows.length > 0 ? (
          <ul className="grid gap-3">
            {rows.map((row, index) => (
              <li key={`${row.channel}-${index}`} className="text-sm leading-relaxed">
                <div className="text-xs text-muted-foreground">{row.sender || row.channel}</div>
                {row.text}
              </li>
            ))}
          </ul>
        ) : (
          <Empty text="Сейчас в эфире тишина. Сохранённые сообщения из журнала ПДА сюда не попадают: движок их скриптам не показывает." />
        )}
      </CardContent>
    </Card>
  )
}

export function StatisticsView({ rows, available }: { rows: PdaStat[] | undefined; available: boolean }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Статистика</CardTitle>
      </CardHeader>
      <CardContent>
        {!available ? (
          <Empty text="Статистика в этой сессии недоступна." />
        ) : (
          <ul className="grid gap-2 sm:grid-cols-2">
            {(rows ?? []).map((row) => (
              <li key={row.id} className="flex items-baseline justify-between gap-3 text-sm">
                <span className="text-muted-foreground">{row.label}</span>
                <span className="font-mono tabular-nums">{row.value}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
