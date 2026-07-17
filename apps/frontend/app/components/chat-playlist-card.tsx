import { Link } from "react-router"
import { Playlist as PlaylistIcon } from "@phosphor-icons/react"

import { trackCoverUrl, type PlaylistChatOut } from "~/lib/api"
import { cn } from "~/lib/utils"

const FALLBACK_COLOR = "#64748b"

export function ChatPlaylistCard({ playlist }: { playlist: PlaylistChatOut }) {
  const preview = (playlist.preview_tracks ?? []).slice(0, 3)

  return (
    <Link
      to={`/playlists/${playlist.id}`}
      className="hover:bg-muted group flex w-fit max-w-[min(40rem,100%)] items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors"
    >
      <PlaylistArt tracks={preview} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium tracking-tight">
          {playlist.title}
        </span>
        <span className="text-muted-foreground block truncate text-xs">
          {playlist.track_count}{" "}
          {playlist.track_count === 1 ? "track" : "tracks"}
          {preview.length > 0
            ? ` · ${preview.map((track) => track.title).join(" · ")}`
            : null}
        </span>
      </span>
      <PlaylistIcon className="text-muted-foreground size-4 shrink-0 opacity-70 group-hover:opacity-100" />
    </Link>
  )
}

export function ChatPlaylistList({
  playlists,
}: {
  playlists: PlaylistChatOut[]
}) {
  if (playlists.length === 0) return null
  return (
    <ul className="flex w-full max-w-[min(40rem,100%)] flex-col gap-1.5">
      {playlists.map((playlist) => (
        <li key={playlist.id}>
          <ChatPlaylistCard playlist={playlist} />
        </li>
      ))}
    </ul>
  )
}

function PlaylistArt({
  tracks,
}: {
  tracks: NonNullable<PlaylistChatOut["preview_tracks"]>
}) {
  if (tracks.length === 0) {
    return (
      <span className="bg-muted text-muted-foreground flex size-11 shrink-0 items-center justify-center rounded-lg">
        <PlaylistIcon className="size-5" weight="duotone" />
      </span>
    )
  }

  if (tracks.length === 1) {
    const track = tracks[0]
    return (
      <span
        className="relative size-11 shrink-0 overflow-hidden rounded-lg"
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
    )
  }

  return (
    <span className="relative h-11 w-14 shrink-0" aria-hidden>
      {tracks.map((track, index) => {
        const fromBack = tracks.length - 1 - index
        const offset = fromBack * 5
        return (
          <span
            key={track.id}
            className={cn(
              "absolute top-0 left-0 size-10 overflow-hidden rounded-md ring-2 ring-background shadow-sm",
            )}
            style={{
              backgroundColor: track.cover_color || FALLBACK_COLOR,
              transform: `translate(${offset}px, ${fromBack}px)`,
              zIndex: index + 1,
            }}
          >
            {track.has_cover ? (
              <img
                src={trackCoverUrl(track.id)}
                alt=""
                className="absolute inset-0 size-full object-cover"
              />
            ) : null}
          </span>
        )
      })}
    </span>
  )
}
