import { useCallback, useState } from "react"
import { Outlet, useMatch, useNavigate, useOutletContext } from "react-router"
import { ClockCounterClockwise } from "@phosphor-icons/react"

import { Button } from "~/components/ui/button"
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "~/components/ui/command"
import { api, type ChatSummaryOut } from "~/lib/api"
import { cn } from "~/lib/utils"
import type { AppOutletContext } from "~/routes/_app"

export default function ChatLayout() {
  const navigate = useNavigate()
  const context = useOutletContext<AppOutletContext>()
  const threadMatch = useMatch("/chat/:chatId")
  const isThread = Boolean(threadMatch)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [chats, setChats] = useState<ChatSummaryOut[] | null>(null)

  const loadChats = useCallback(() => {
    setChats(null)
    void api.v1.listChats().then((result) => {
      if (result.error || !result.data) {
        setChats([])
        return
      }
      setChats(result.data)
    })
  }, [])

  return (
    <div
      className={cn(
        "relative mx-auto flex h-full min-h-0 w-full max-w-4xl flex-col",
        isThread ? "px-6 pt-6" : "px-6",
      )}
    >
      <div
        className={cn(
          "flex shrink-0 items-start justify-between gap-4",
          isThread ? "pb-4" : "absolute top-4 right-6 z-20",
        )}
      >
        {isThread ? (
          <div className="flex min-w-0 flex-col gap-1">
            <h1 className="text-2xl font-medium tracking-tight">Chat</h1>
            <p className="text-muted-foreground text-sm">
              Ask your library in natural language.
            </p>
          </div>
        ) : (
          <span className="sr-only">Chat</span>
        )}
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="shrink-0"
          onClick={() => {
            setHistoryOpen(true)
            loadChats()
          }}
        >
          <ClockCounterClockwise data-icon="inline-start" />
          History
        </Button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col">
        <Outlet context={context} />
      </div>

      <CommandDialog
        open={historyOpen}
        onOpenChange={setHistoryOpen}
        title="Chat history"
        description="Search and open a previous chat."
      >
        <Command>
          <CommandInput placeholder="Search chats…" />
          <CommandList>
            <CommandEmpty>
              {chats === null ? "Loading…" : "No chats found."}
            </CommandEmpty>
            {chats && chats.length > 0 ? (
              <CommandGroup heading="Recent">
                {chats.map((chat) => (
                  <CommandItem
                    key={chat.id}
                    value={`${chat.title} ${chat.id}`}
                    onSelect={() => {
                      setHistoryOpen(false)
                      void navigate(`/chat/${chat.id}`)
                    }}
                  >
                    <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className="truncate">{chat.title}</span>
                      <span className="text-muted-foreground text-xs">
                        {new Date(chat.updated_at).toLocaleString()}
                      </span>
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            ) : null}
          </CommandList>
        </Command>
      </CommandDialog>
    </div>
  )
}
