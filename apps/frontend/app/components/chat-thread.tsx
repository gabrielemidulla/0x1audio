import { useMemo } from "react"

import { ChatActivity, type ChatActivityStep } from "~/components/chat-activity"
import { ChatMarkdown } from "~/components/chat-markdown"
import { ChatPlaylistList } from "~/components/chat-playlist-card"
import { ChatTrackList } from "~/components/chat-track-list"
import type { ChatMessageOut, PlaylistChatOut, TrackOut } from "~/lib/api"
import { cn } from "~/lib/utils"

export type ThreadMessage = ChatMessageOut & {
  thinking?: boolean
  activity?: ChatActivityStep[]
}

type ChatThreadProps = {
  messages: ThreadMessage[]
  tracksById: Map<string, TrackOut>
  playlistsById: Map<string, PlaylistChatOut>
}

export function ChatThread({
  messages,
  tracksById,
  playlistsById,
}: ChatThreadProps) {
  return (
    <div className="flex flex-col gap-4">
      {messages.map((message) => (
        <MessageBlock
          key={message.id}
          message={message}
          tracksById={tracksById}
          playlistsById={playlistsById}
        />
      ))}
    </div>
  )
}

function MessageBlock({
  message,
  tracksById,
  playlistsById,
}: {
  message: ThreadMessage
  tracksById: Map<string, TrackOut>
  playlistsById: Map<string, PlaylistChatOut>
}) {
  const tracks = useMemo(() => {
    if (message.role !== "assistant" || !message.track_ids?.length) return []
    return message.track_ids
      .map((id) => tracksById.get(id))
      .filter((track): track is TrackOut => track != null)
  }, [message, tracksById])

  const playlists = useMemo(() => {
    if (message.role !== "assistant" || !message.playlist_ids?.length) return []
    return message.playlist_ids
      .map((id) => playlistsById.get(id))
      .filter((playlist): playlist is PlaylistChatOut => playlist != null)
  }, [message, playlistsById])

  const isUser = message.role === "user"
  const activity = message.activity ?? []
  const showActivity = Boolean(message.thinking) && activity.length > 0 && !message.content
  const showThinkingFallback =
    Boolean(message.thinking) && !message.content && activity.length === 0

  return (
    <div className={cn("flex flex-col gap-2", isUser ? "items-end" : "items-start")}>
      <div
        className={cn(
          "max-w-[min(40rem,100%)] text-sm leading-relaxed transition-colors duration-300",
          isUser
            ? "rounded-2xl bg-muted px-4 py-2.5 text-foreground"
            : "px-1 py-0.5 text-foreground",
        )}
      >
        {showActivity ? (
          <ChatActivity steps={activity} />
        ) : showThinkingFallback ? (
          <ChatActivity
            steps={[{ id: "thinking", kind: "thinking", label: "Thinking" }]}
          />
        ) : (
          <div className="relative animate-in fade-in duration-300">
            <ChatMarkdown content={message.content} />
            {message.thinking ? (
              <span className="bg-foreground/70 ml-0.5 inline-block h-3.5 w-1.5 animate-pulse align-middle" />
            ) : null}
          </div>
        )}
      </div>
      <ChatPlaylistList playlists={playlists} />
      <ChatTrackList tracks={tracks} />
    </div>
  )
}
