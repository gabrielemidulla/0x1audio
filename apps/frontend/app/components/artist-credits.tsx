import { Link } from "react-router"

import type { ArtistRefOut, TrackOut } from "~/lib/api"
import { cn } from "~/lib/utils"

type ArtistCreditsProps = {
  track: Pick<TrackOut, "artist" | "artists">
  className?: string
  maxVisible?: number
  link?: boolean
}

function creditList(track: Pick<TrackOut, "artist" | "artists">): ArtistRefOut[] {
  if (track.artists && track.artists.length > 0) return track.artists
  const fallback = track.artist?.trim()
  if (!fallback) return []
  return [{ id: "", name: fallback }]
}

export function ArtistCredits({
  track,
  className,
  maxVisible = 2,
  link = true,
}: ArtistCreditsProps) {
  const artists = creditList(track)
  if (artists.length === 0) {
    return (
      <span className={cn("text-muted-foreground", className)}>
        Unknown artist
      </span>
    )
  }

  const visible = artists.slice(0, maxVisible)
  const overflow = artists.length - visible.length

  return (
    <span
      className={cn(
        "text-muted-foreground inline min-w-0 truncate",
        className,
      )}
    >
      {visible.map((artist, index) => (
        <span key={artist.id || `${artist.name}-${index}`}>
          {index > 0 ? ", " : null}
          {link && artist.id ? (
            <Link
              to={`/catalog/artists/${artist.id}`}
              className="text-inherit underline-offset-2 hover:underline"
              onClick={(event) => event.stopPropagation()}
            >
              {artist.name}
            </Link>
          ) : (
            artist.name
          )}
        </span>
      ))}
      {overflow > 0 ? ` +${overflow}` : null}
    </span>
  )
}

export function artistCreditsText(
  track: Pick<TrackOut, "artist" | "artists">,
): string {
  const artists = creditList(track)
  if (artists.length === 0) return "Unknown artist"
  return artists.map((artist) => artist.name).join(", ")
}
