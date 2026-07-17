import { startTransition, useEffect, useMemo, useRef, useState } from "react"
import { Link, useLocation, useNavigate, useParams } from "react-router"

import {
  activityFromStatus,
  type ChatActivityStep,
} from "~/components/chat-activity"
import { ChatComposerDock } from "~/components/chat-composer-dock"
import { ChatPrompter } from "~/components/chat-prompter"
import { ChatThread, type ThreadMessage } from "~/components/chat-thread"
import { streamChatMessage, streamChatReply } from "~/lib/chat-stream"
import { api, type ChatDetailOut, type PlaylistChatOut, type TrackOut } from "~/lib/api"

type ChatLocationState = {
  seed?: ChatDetailOut
}

function tempId(prefix: string): string {
  const id =
    globalThis.crypto?.randomUUID?.() ??
    `tmp-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
  return `${prefix}-${id}`
}

function nowIso(): string {
  return new Date().toISOString()
}

export default function ChatThreadPage() {
  const { chatId } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const locationSeed = (location.state as ChatLocationState | null)?.seed
  const initialSeed =
    locationSeed && chatId && locationSeed.id === chatId ? locationSeed : null

  const [messages, setMessages] = useState<ThreadMessage[] | null>(
    () => initialSeed?.messages ?? null,
  )
  const [tracks, setTracks] = useState<TrackOut[]>(
    () => initialSeed?.tracks ?? [],
  )
  const [playlists, setPlaylists] = useState<PlaylistChatOut[]>(
    () => initialSeed?.playlists ?? [],
  )
  const [error, setError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const replyStartedFor = useRef<string | null>(null)
  const assistantLocalId = useRef<string | null>(null)
  const generatingRef = useRef(false)

  useEffect(() => {
    generatingRef.current = generating
  }, [generating])

  useEffect(() => {
    if (!chatId) return

    let cancelled = false
    const seeded =
      locationSeed && locationSeed.id === chatId ? locationSeed : null

    // Reset reply tracking for this chat load; do not abort mid-flight here —
    // Strict Mode remounts would cancel a healthy stream and poison the DB pool.
    replyStartedFor.current = null
    setGenerating(false)
    generatingRef.current = false
    setError(null)

    if (seeded) {
      setMessages((prev) => {
        if (prev?.some((message) => message.thinking)) return prev
        return seeded.messages
      })
      setTracks((prev) => (prev.length > 0 ? prev : (seeded.tracks ?? [])))
      setPlaylists((prev) =>
        prev.length > 0 ? prev : (seeded.playlists ?? []),
      )
      // Drop one-shot navigation state so refresh uses the API.
      navigate(location.pathname, { replace: true, state: null })
    } else {
      setMessages(null)
      setTracks([])
      setPlaylists([])
    }

    void api.v1.getChat({ path: { chat_id: chatId } }).then((result) => {
      if (cancelled) return
      // Don't clobber an in-flight optimistic/streaming thread.
      if (generatingRef.current || replyStartedFor.current) return
      if (result.error || !result.data) {
        if (!seeded) {
          setError("Could not load chat")
          setMessages([])
        }
        return
      }
      setMessages((prev) => {
        if (prev?.some((message) => message.thinking)) return prev
        return result.data.messages
      })
      setTracks(result.data.tracks ?? [])
      setPlaylists(result.data.playlists ?? [])
    })

    return () => {
      cancelled = true
    }
    // Only re-load when the chat id changes; seed is applied once above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatId])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
      abortRef.current = null
    }
  }, [chatId])

  useEffect(() => {
    if (!chatId || !messages || generating) return
    const last = messages.at(-1)
    if (!last || last.role !== "user") return
    if (replyStartedFor.current === last.id) return

    // Defer so React Strict Mode's effect→cleanup→effect cycle cancels the
    // first timer and only the remount actually starts a stream.
    const timer = window.setTimeout(() => {
      if (replyStartedFor.current === last.id) return
      replyStartedFor.current = last.id
      void startReply()
    }, 0)

    return () => {
      window.clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatId, messages, generating])

  const tracksById = useMemo(() => {
    const map = new Map<string, TrackOut>()
    for (const track of tracks) {
      map.set(track.id, track)
    }
    return map
  }, [tracks])

  const playlistsById = useMemo(() => {
    const map = new Map<string, PlaylistChatOut>()
    for (const playlist of playlists) {
      map.set(playlist.id, playlist)
    }
    return map
  }, [playlists])

  function mergeTracks(incoming: TrackOut[]) {
    setTracks((prev) => {
      const byId = new Map(prev.map((track) => [track.id, track]))
      for (const track of incoming) {
        byId.set(track.id, track)
      }
      return [...byId.values()]
    })
  }

  function mergePlaylists(incoming: PlaylistChatOut[]) {
    setPlaylists((prev) => {
      const byId = new Map(prev.map((playlist) => [playlist.id, playlist]))
      for (const playlist of incoming) {
        byId.set(playlist.id, playlist)
      }
      return [...byId.values()]
    })
  }

  function patchAssistant(
    localId: string,
    patch: Partial<ThreadMessage> | ((current: ThreadMessage) => ThreadMessage),
  ) {
    setMessages((prev) => {
      if (!prev) return prev
      return prev.map((message) => {
        if (message.id !== localId) return message
        return typeof patch === "function" ? patch(message) : { ...message, ...patch }
      })
    })
  }

  function beginAssistantPlaceholder(): string {
    const id = tempId("assistant")
    assistantLocalId.current = id
    setMessages((prev) => [
      ...(prev ?? []),
      {
        id,
        role: "assistant",
        content: "",
        created_at: nowIso(),
        thinking: true,
        activity: [{ id: "thinking", kind: "thinking", label: "Thinking" }],
      },
    ])
    return id
  }

  function pushActivity(localId: string, step: ChatActivityStep) {
    startTransition(() => {
      patchAssistant(localId, (current) => {
        const previous = current.activity ?? []
        const last = previous.at(-1)

        if (step.kind === "thinking") {
          if (last?.kind === "thinking" && !last.done) return current
          const marked = previous.map((item) =>
            item.done ? item : { ...item, done: true },
          )
          return {
            ...current,
            thinking: true,
            activity: [...marked, step],
          }
        }

        // Tool step: drop the idle thinking placeholder, mark prior steps done.
        const withoutThinking = previous.filter((item) => item.kind !== "thinking")
        if (
          last?.kind === "tool" &&
          !last.done &&
          last.name === step.name
        ) {
          return current
        }
        const marked = withoutThinking.map((item) =>
          item.done ? item : { ...item, done: true },
        )
        return {
          ...current,
          thinking: true,
          activity: [...marked, step],
        }
      })
    })
  }

  async function startReply() {
    if (!chatId) return
    const controller = new AbortController()
    abortRef.current?.abort()
    abortRef.current = controller
    setGenerating(true)
    generatingRef.current = true
    setError(null)
    const localId = beginAssistantPlaceholder()

    try {
      await streamChatReply(
        chatId,
        {
          onStatus: (phase, name) => {
            const step = activityFromStatus(phase, name)
            if (step) pushActivity(localId, step)
          },
          onToken: (text) => {
            patchAssistant(localId, (current) => ({
              ...current,
              content: current.content + text,
              thinking: true,
              activity: undefined,
            }))
          },
          onDone: ({ message, tracks: nextTracks, playlists: nextPlaylists, cancelled: wasCancelled }) => {
            if (message) {
              patchAssistant(localId, {
                ...message,
                thinking: false,
                activity: undefined,
              })
            } else if (wasCancelled) {
              setMessages((prev) => prev?.filter((m) => m.id !== localId) ?? null)
            } else {
              patchAssistant(localId, { thinking: false, activity: undefined })
            }
            mergeTracks(nextTracks)
            mergePlaylists(nextPlaylists)
          },
          onError: (detail) => {
            setError(detail)
            setMessages((prev) => prev?.filter((m) => m.id !== localId) ?? null)
          },
        },
        controller.signal,
      )
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setMessages((prev) => {
          if (!prev) return prev
          return prev.flatMap((message) => {
            if (message.id !== localId) return [message]
            if (!message.content.trim()) return []
            return [{ ...message, thinking: false, activity: undefined }]
          })
        })
      } else {
        setError("Could not generate reply")
        setMessages((prev) => prev?.filter((m) => m.id !== localId) ?? null)
      }
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null
      }
      setGenerating(false)
      generatingRef.current = false
      assistantLocalId.current = null
    }
  }

  async function sendMessage(message: string) {
    if (!chatId) return
    const controller = new AbortController()
    abortRef.current?.abort()
    abortRef.current = controller
    setGenerating(true)
    generatingRef.current = true
    setError(null)

    const userLocalId = tempId("user")
    const assistantId = tempId("assistant")
    assistantLocalId.current = assistantId
    replyStartedFor.current = userLocalId

    setMessages((prev) => [
      ...(prev ?? []),
      {
        id: userLocalId,
        role: "user",
        content: message,
        created_at: nowIso(),
      },
      {
        id: assistantId,
        role: "assistant",
        content: "",
        created_at: nowIso(),
        thinking: true,
        activity: [{ id: "thinking", kind: "thinking", label: "Thinking" }],
      },
    ])

    try {
      await streamChatMessage(
        chatId,
        message,
        {
          onUser: (persisted) => {
            replyStartedFor.current = persisted.id
            setMessages((prev) =>
              prev?.map((item) =>
                item.id === userLocalId ? { ...persisted } : item,
              ) ?? null,
            )
          },
          onStatus: (phase, name) => {
            const step = activityFromStatus(phase, name)
            if (step) pushActivity(assistantId, step)
          },
          onToken: (text) => {
            patchAssistant(assistantId, (current) => ({
              ...current,
              content: current.content + text,
              thinking: true,
              activity: undefined,
            }))
          },
          onDone: ({ message: assistant, tracks: nextTracks, playlists: nextPlaylists, cancelled: wasCancelled }) => {
            if (assistant) {
              patchAssistant(assistantId, {
                ...assistant,
                thinking: false,
                activity: undefined,
              })
            } else if (wasCancelled) {
              setMessages((prev) => prev?.filter((m) => m.id !== assistantId) ?? null)
            } else {
              patchAssistant(assistantId, { thinking: false, activity: undefined })
            }
            mergeTracks(nextTracks)
            mergePlaylists(nextPlaylists)
          },
          onError: (detail) => {
            setError(detail)
            setMessages(
              (prev) =>
                prev?.filter(
                  (m) => m.id !== assistantId && m.id !== userLocalId,
                ) ?? null,
            )
          },
        },
        controller.signal,
      )
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setMessages((prev) => {
          if (!prev) return prev
          return prev.flatMap((message) => {
            if (message.id !== assistantId) return [message]
            if (!message.content.trim()) return []
            return [{ ...message, thinking: false, activity: undefined }]
          })
        })
      } else {
        setError("Could not send message")
        setMessages(
          (prev) =>
            prev?.filter((m) => m.id !== assistantId && m.id !== userLocalId) ??
            null,
        )
      }
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null
      }
      setGenerating(false)
      generatingRef.current = false
      assistantLocalId.current = null
    }
  }

  if (!chatId) {
    return <p className="text-destructive text-sm">Missing chat id</p>
  }

  if (error && messages === null) {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-destructive text-sm">{error}</p>
        <Link to="/chat" className="text-sm underline">
          Start a new chat
        </Link>
      </div>
    )
  }

  if (messages === null) {
    return <p className="text-muted-foreground text-sm">Loading…</p>
  }

  return (
    <ChatComposerDock
      scrollKey={`${messages.length}:${messages.at(-1)?.content.length ?? 0}:${generating}`}
      composer={
        <ChatPrompter
          generating={generating}
          onStop={() => abortRef.current?.abort()}
          onSubmit={(message) => sendMessage(message)}
        />
      }
    >
      <div className="flex flex-col gap-6">
        <ChatThread
          messages={messages}
          tracksById={tracksById}
          playlistsById={playlistsById}
        />
        {error ? <p className="text-destructive text-sm">{error}</p> : null}
      </div>
    </ChatComposerDock>
  )
}
