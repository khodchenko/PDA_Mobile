import { Activity, BookOpen, ChartColumn, Gauge, ListChecks, Mail, Map as MapIcon, Shield, Users } from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import { toast } from "sonner"

import { LinkBanner } from "@/components/pda/link-banner"
import { LinkView } from "@/components/pda/link-view"
import { MapView } from "@/components/pda/map-view"
import { PairScreen } from "@/components/pda/pair-screen"
import {
  ContactsView,
  EncyclopediaView,
  MessagesView,
  RelationsView,
  StatisticsView,
  TasksView,
} from "@/components/pda/sections-view"
import { StatusView } from "@/components/pda/status-view"
import { TopBar } from "@/components/pda/top-bar"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Toaster } from "@/components/ui/sonner"
import { useBridge } from "@/hooks/use-bridge"
import { useNow } from "@/hooks/use-now"
import { describeChain } from "@/lib/link"

const TABS = [
  { value: "status", label: "Статус", icon: Gauge },
  { value: "map", label: "Карта", icon: MapIcon },
  { value: "tasks", label: "Задания", icon: ListChecks },
  { value: "relations", label: "Группы", icon: Shield },
  { value: "contacts", label: "Контакты", icon: Users },
  { value: "guide", label: "Справочник", icon: BookOpen },
  { value: "messages", label: "Сообщения", icon: Mail },
  { value: "stats", label: "Статистика", icon: ChartColumn },
  { value: "link", label: "Связь", icon: Activity },
] as const

export default function App() {
  const bridge = useBridge()
  const now = useNow(1000)
  const [tab, setTab] = useState<string>("status")
  const sinceMessageMs = bridge.lastMessageAt === null ? null : Math.max(0, now - bridge.lastMessageAt)
  const chain = useMemo(
    () => describeChain({ status: bridge.status, reconnects: bridge.reconnects, sinceMessageMs }, bridge.state),
    [bridge.status, bridge.reconnects, sinceMessageMs, bridge.state],
  )
  const fast = bridge.state?.fast ?? null
  const slow = bridge.state?.slow ?? null

  const shownTransition = useRef<number | null>(null)
  const latest = bridge.transitions[0]
  useEffect(() => {
    if (!latest || shownTransition.current === latest.id) return
    shownTransition.current = latest.id
    toast(`Переход: ${latest.to}`, { description: `Из локации «${latest.from}»` })
  }, [latest])

  if (bridge.status === "unpaired" && !bridge.pairing) {
    return <PairScreen onPair={bridge.pairWith} />
  }

  return (
    <div className="min-h-dvh">
      <TopBar chain={chain} fast={fast} />
      <Tabs value={tab} onValueChange={setTab} className="mx-auto max-w-5xl gap-4 px-4 pt-4 pb-28 md:pb-10">
        <TabsList className="fixed inset-x-0 bottom-0 z-30 flex h-auto w-full justify-start overflow-x-auto rounded-none border-t border-border/60 bg-background/95 p-1.5 pb-[max(0.375rem,env(safe-area-inset-bottom))] backdrop-blur md:static md:rounded-lg md:border md:bg-muted md:p-[3px]">
          {TABS.map(({ value, label, icon: Icon }) => (
            <TabsTrigger
              key={value}
              value={value}
              className="h-14 min-w-16 flex-none flex-col gap-1 px-2 text-[11px] md:h-8 md:min-w-0 md:flex-row md:gap-1.5 md:px-3 md:text-sm"
            >
              <Icon className="size-5 md:size-4" />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        {tab !== "link" && <LinkBanner chain={chain} fast={fast} />}

        <TabsContent value="status">
          <StatusView fast={fast} slow={slow} />
        </TabsContent>
        <TabsContent value="map">
          <MapView fast={fast} trail={bridge.trail} transitions={bridge.transitions} map={bridge.state?.map ?? null} token={bridge.token} />
        </TabsContent>
        <TabsContent value="tasks">
          <TasksView tasks={slow?.tasks} available={!!slow?.capabilities?.tasks} />
        </TabsContent>
        <TabsContent value="relations">
          <RelationsView rows={slow?.relations} available={!!slow?.capabilities?.relations} />
        </TabsContent>
        <TabsContent value="contacts">
          <ContactsView rows={slow?.contacts} available={!!slow?.capabilities?.contacts} />
        </TabsContent>
        <TabsContent value="guide">
          <EncyclopediaView rows={slow?.encyclopedia} available={!!slow?.capabilities?.encyclopedia} />
        </TabsContent>
        <TabsContent value="messages">
          <MessagesView rows={slow?.messages} available={!!slow?.capabilities?.messages} />
        </TabsContent>
        <TabsContent value="stats">
          <StatisticsView rows={slow?.statistics} available={!!slow?.capabilities?.statistics} />
        </TabsContent>
        <TabsContent value="link">
          <LinkView
            chain={chain}
            state={bridge.state}
            pairing={bridge.pairing}
            log={bridge.log}
            onForget={bridge.forget}
          />
        </TabsContent>
      </Tabs>
      <Toaster theme="dark" position="top-center" />
    </div>
  )
}
