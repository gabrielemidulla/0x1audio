import type {
  ChatMessageOut,
  PlaylistChatOut,
  TrackOut,
} from "~/lib/api"

export type ChatStreamStatusPhase = "thinking" | "tool" | "cancelled"

export type ChatStreamHandlers = {
  onUser?: (message: ChatMessageOut) => void
  onStatus?: (phase: ChatStreamStatusPhase, name?: string | null) => void
  onToken?: (text: string) => void
  onTitle?: (title: string) => void
  onDone?: (payload: {
    message: ChatMessageOut | null
    tracks: TrackOut[]
    playlists: PlaylistChatOut[]
    cancelled: boolean
  }) => void
  onError?: (detail: string) => void
}

type StreamEvent = {
  type: string
  message?: ChatMessageOut | null
  text?: string
  title?: string
  phase?: ChatStreamStatusPhase
  name?: string | null
  tracks?: TrackOut[]
  playlists?: PlaylistChatOut[]
  cancelled?: boolean
  detail?: string
}

async function readSse(
  response: Response,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  if (!response.body) {
    throw new Error("No response body")
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split("\n\n")
    buffer = parts.pop() ?? ""
    for (const part of parts) {
      const dataLine = part
        .split("\n")
        .map((line) => line.trimEnd())
        .find((line) => line.startsWith("data:"))
      if (!dataLine) continue
      const raw = dataLine.replace(/^data:\s?/, "")
      if (!raw || raw === "[DONE]") continue
      onEvent(JSON.parse(raw) as StreamEvent)
    }
  }
}

function handleEvent(event: StreamEvent, handlers: ChatStreamHandlers): void {
  switch (event.type) {
    case "user":
      if (event.message) handlers.onUser?.(event.message)
      break
    case "status":
      if (event.phase) handlers.onStatus?.(event.phase, event.name)
      break
    case "token":
      if (event.text) handlers.onToken?.(event.text)
      break
    case "title":
      if (event.title) handlers.onTitle?.(event.title)
      break
    case "done":
      handlers.onDone?.({
        message: event.message ?? null,
        tracks: event.tracks ?? [],
        playlists: event.playlists ?? [],
        cancelled: Boolean(event.cancelled),
      })
      break
    case "error":
      handlers.onError?.(event.detail || "Chat failed")
      break
    default:
      break
  }
}

async function streamPost(
  path: string,
  body: unknown | undefined,
  signal: AbortSignal | undefined,
  handlers: ChatStreamHandlers,
): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    credentials: "include",
    headers: body ? { "Content-Type": "application/json", Accept: "text/event-stream" } : { Accept: "text/event-stream" },
    body: body ? JSON.stringify(body) : undefined,
    signal,
  })
  if (!response.ok) {
    handlers.onError?.(`Request failed (${response.status})`)
    return
  }
  await readSse(response, (event) => {
    handleEvent(event, handlers)
  })
}

export function streamChatReply(
  chatId: string,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  return streamPost(`/api/v1/chats/${chatId}/reply/stream`, undefined, signal, handlers)
}

export function streamChatMessage(
  chatId: string,
  message: string,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  return streamPost(
    `/api/v1/chats/${chatId}/messages/stream`,
    { message },
    signal,
    handlers,
  )
}
