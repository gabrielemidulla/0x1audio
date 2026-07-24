import { useCallback, useEffect, useState } from "react"
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
import { Reveal } from "~/components/reveal"
import { SlidingHoverList } from "~/components/sliding-hover-list"
import { Skeleton } from "~/components/ui/skeleton"
import { Spinner } from "~/components/ui/spinner"
import { api, type ChatSummaryOut } from "~/lib/api"
import { hasChatEntered, markChatEntered } from "~/lib/chat-cache"
import { cn } from "~/lib/utils"
import type { AppOutletContext } from "~/routes/_app"

export type ChatOutletContext = AppOutletContext & {
  chatTitle: string
  setChatTitle: (title: string) => void
}

function chatTitlePending(title: string | null | undefined): boolean {
  return !title?.trim()
}

export default function ChatLayout() {
  const navigate = useNavigate()
  const context = useOutletContext<AppOutletContext>()
  const threadMatch = useMatch("/chat/:chatId")
  const isThread = Boolean(threadMatch)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [chats, setChats] = useState<ChatSummaryOut[] | null>(null)
  const [chatTitle, setChatTitle] = useState("")
  const alreadyEntered = hasChatEntered()
  const [pageIn, setPageIn] = useState(alreadyEntered)

  useEffect(() => {
    if (alreadyEntered) {
      setPageIn(true)
      return
    }
    const timer = window.setTimeout(() => {
      setPageIn(true)
      markChatEntered()
    }, 50)
    return () => window.clearTimeout(timer)
  }, [alreadyEntered])

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

  const outletContext: ChatOutletContext = {
    ...context,
    chatTitle,
    setChatTitle,
  }

  return (
    <Reveal
      visible={pageIn}
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
          <div className="flex min-w-0 flex-1 items-center pt-0.5">
            {chatTitlePending(chatTitle) ? (
              <Skeleton
                className="h-8 w-48 max-w-full"
                aria-label="Generating chat title"
              />
            ) : (
              <h1 className="truncate text-2xl font-medium tracking-tight">
                {chatTitle}
              </h1>
            )}
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
        <Outlet context={outletContext} />
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
              {chats === null ? (
                <span className="inline-flex items-center gap-2">
                  <Spinner className="size-4" />
                  Loading chats
                </span>
              ) : (
                "No chats found."
              )}
            </CommandEmpty>
            {chats && chats.length > 0 ? (
              <CommandGroup heading="Recent">
                <SlidingHoverList
                  followSelected
                  className="flex flex-col gap-0.5"
                  indicatorClassName="rounded-lg bg-muted"
                >
                  {chats.map((chat) => (
                    <CommandItem
                      key={chat.id}
                      data-sliding-item
                      value={
                        chatTitlePending(chat.title)
                          ? `untitled ${chat.id}`
                          : `${chat.title} ${chat.id}`
                      }
                      className="relative z-[1] data-selected:bg-transparent"
                      onSelect={() => {
                        setHistoryOpen(false)
                        void navigate(`/chat/${chat.id}`)
                      }}
                    >
                      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                        {chatTitlePending(chat.title) ? (
                          <Skeleton className="h-4 w-36" />
                        ) : (
                          <span className="truncate">{chat.title}</span>
                        )}
                        <span className="text-muted-foreground text-xs">
                          {new Date(chat.updated_at).toLocaleString()}
                        </span>
                      </div>
                    </CommandItem>
                  ))}
                </SlidingHoverList>
              </CommandGroup>
            ) : null}
          </CommandList>
        </Command>
      </CommandDialog>
    </Reveal>
  )
}
