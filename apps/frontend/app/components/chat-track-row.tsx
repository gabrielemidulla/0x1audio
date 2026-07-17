import { Pause, Play } from "@phosphor-icons/react"

import { trackCoverUrl, type TrackOut } from "~/lib/api"
import { toggleTrack, useAudioPlayer } from "~/lib/audio-player"
import { cn } from "~/lib/utils"

const FALLBACK_COLOR = "#64748b"

export function ChatTrackRow({ track }: { track: TrackOut }) {
  const player = useAudioPlayer()
  const isActive = player.track?.id === track.id
  const isPlaying = isActive && player.playing

  return (
    <button
      type="button"
      className={cn(
        "group hover:bg-muted flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left",
        isActive && "bg-muted/70",
      )}
      onClick={() => {
        void toggleTrack(track)
      }}
    >
      <span className="relative shrink-0">
        <span
          className="relative block size-9 overflow-hidden rounded-md bg-muted"
          style={{ backgroundColor: track.cover_color || FALLBACK_COLOR }}
        >
          {track.has_cover ? (
            <img
              src={trackCoverUrl(track.id)}
              alt=""
              className="absolute inset-0 size-full object-cover"
            />
          ) : null}
        </span>
        <span
          className={cn(
            "absolute inset-0 flex items-center justify-center rounded-md bg-black/45 text-white opacity-0 transition-opacity",
            "group-hover:opacity-100",
            isPlaying && "opacity-100",
          )}
        >
          {isPlaying ? (
            <Pause weight="fill" className="size-3.5" />
          ) : (
            <Play weight="fill" className="size-3.5" />
          )}
        </span>
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{track.title}</span>
        <span className="text-muted-foreground block truncate text-xs">
          {track.artist || "Unknown artist"}
        </span>
      </span>
    </button>
  )
}
