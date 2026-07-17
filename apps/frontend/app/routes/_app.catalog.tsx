import { useEffect, useState } from "react"
import { Link } from "react-router"
import { Graph, Pause, Play } from "@phosphor-icons/react"

import { api, trackCoverUrl, type TrackOut, type TrackStatus } from "~/lib/api"
import { toggleTrack, useAudioPlayer } from "~/lib/audio-player"
import { Badge } from "~/components/ui/badge"
import { Button } from "~/components/ui/button"
import { Input } from "~/components/ui/input"
import { Label } from "~/components/ui/label"
import { cn } from "~/lib/utils"

const ACCEPT_AUDIO = ".mp3,.wav,.flac,.m4a,.ogg,.aac"
const PENDING_TRACK: TrackStatus[] = ["uploading", "queued", "indexing"]
const FALLBACK_COLOR = "#64748b"

function statusVariant(status: string) {
  if (status === "ready" || status === "complete") return "default" as const
  if (status === "failed") return "destructive" as const
  return "secondary" as const
}

function TrackArt({ track }: { track: TrackOut }) {
  return (
    <div
      className="relative size-10 shrink-0 overflow-hidden rounded-md bg-muted"
      style={{ backgroundColor: track.cover_color || FALLBACK_COLOR }}
    >
      {track.has_cover ? (
        <img
          src={trackCoverUrl(track.id)}
          alt=""
          className="absolute inset-0 size-full object-cover"
        />
      ) : null}
    </div>
  )
}

export default function CatalogPage() {
  const [tracks, setTracks] = useState<TrackOut[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const player = useAudioPlayer()

  async function refresh() {
    const tracksResult = await api.v1.listTracks()
    if (tracksResult.error || !tracksResult.data) {
      setError("Could not load tracks")
      return
    }
    setError(null)
    setTracks(tracksResult.data)
  }

  useEffect(() => {
    void refresh()
  }, [])

  useEffect(() => {
    const tracksPending = tracks?.some((track) =>
      PENDING_TRACK.includes(track.status),
    )
    if (!tracksPending) return
    const id = window.setInterval(() => {
      void refresh()
    }, 2000)
    return () => window.clearInterval(id)
  }, [tracks])

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-medium tracking-tight">Catalog</h1>
        <p className="text-muted-foreground text-sm leading-relaxed">
          Upload audio files or a ZIP of tracks to index them. Track indexing
          progress under{" "}
          <Link
            to="/jobs"
            className="text-foreground underline-offset-4 hover:underline"
          >
            Jobs
          </Link>
          .
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <form
          className="flex flex-col gap-3"
          onSubmit={async (event) => {
            event.preventDefault()
            const form = new FormData(event.currentTarget)
            const file = form.get("file")
            if (!(file instanceof File) || file.size === 0) {
              setError("Choose a file first")
              return
            }
            setUploading(true)
            setError(null)
            const { error: apiError } = await api.v1.uploadTrack({
              body: { file },
            })
            setUploading(false)
            if (apiError) {
              setError("Upload failed")
              return
            }
            event.currentTarget.reset()
            await refresh()
          }}
        >
          <div className="flex flex-col gap-2">
            <Label htmlFor="track-file">Audio file</Label>
            <Input
              id="track-file"
              name="file"
              type="file"
              accept={ACCEPT_AUDIO}
              disabled={uploading}
              required
            />
          </div>
          <Button type="submit" disabled={uploading}>
            {uploading ? "Uploading…" : "Upload file"}
          </Button>
        </form>

        <form
          className="flex flex-col gap-3"
          onSubmit={async (event) => {
            event.preventDefault()
            const form = new FormData(event.currentTarget)
            const file = form.get("file")
            if (!(file instanceof File) || file.size === 0) {
              setError("Choose a ZIP first")
              return
            }
            setUploading(true)
            setError(null)
            const { error: apiError } = await api.v1.uploadZip({
              body: { file },
            })
            setUploading(false)
            if (apiError) {
              setError("ZIP upload failed")
              return
            }
            event.currentTarget.reset()
            await refresh()
          }}
        >
          <div className="flex flex-col gap-2">
            <Label htmlFor="zip-file">ZIP archive</Label>
            <Input
              id="zip-file"
              name="file"
              type="file"
              accept=".zip,application/zip"
              disabled={uploading}
              required
            />
          </div>
          <Button type="submit" disabled={uploading}>
            {uploading ? "Uploading…" : "Upload ZIP"}
          </Button>
        </form>
      </div>

      {error ? <p className="text-destructive text-sm">{error}</p> : null}

      {tracks === null ? (
        <p className="text-muted-foreground text-sm">Loading…</p>
      ) : tracks.length === 0 ? (
        <p className="text-muted-foreground text-sm">No tracks yet.</p>
      ) : (
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-medium">Tracks</h2>
          <ul className="flex flex-col gap-0.5">
            {tracks.map((track) => {
              const isActive = player.track?.id === track.id
              const isPlaying = isActive && player.playing
              const canPlay = track.status === "ready"

              return (
                <li key={track.id}>
                  <div
                    className={cn(
                      "group flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left",
                      canPlay && "hover:bg-muted cursor-pointer",
                      isActive && "bg-muted/70",
                    )}
                    role={canPlay ? "button" : undefined}
                    tabIndex={canPlay ? 0 : undefined}
                    onClick={() => {
                      if (!canPlay) return
                      void toggleTrack(track)
                    }}
                    onKeyDown={(event) => {
                      if (!canPlay) return
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault()
                        void toggleTrack(track)
                      }
                    }}
                  >
                    <span className="relative shrink-0">
                      <TrackArt track={track} />
                      {canPlay ? (
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
                      ) : null}
                    </span>

                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">
                        {track.title}
                      </span>
                      <span className="text-muted-foreground block truncate text-sm">
                        {track.artist || "Unknown artist"}
                      </span>
                      {track.status === "failed" && track.error_message ? (
                        <span className="text-destructive mt-0.5 block truncate text-xs">
                          {track.error_message}
                        </span>
                      ) : null}
                    </span>

                    {track.status !== "ready" ? (
                      <Badge variant={statusVariant(track.status)}>
                        {track.status}
                      </Badge>
                    ) : (
                      <Button
                        type="button"
                        size="icon-sm"
                        variant="ghost"
                        className="opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                        aria-label="Explore in graph"
                        render={<Link to={`/graph?focus=${track.id}`} />}
                        onClick={(event) => event.stopPropagation()}
                      >
                        <Graph weight="regular" />
                      </Button>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      )}
    </div>
  )
}
