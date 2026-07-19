import { useEffect, useMemo, useState } from "react"
import { Link, useLocation, useNavigate, useParams } from "react-router"
import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  MagnifyingGlass,
  Pause,
  PencilSimple,
  Play,
  Plus,
  Trash,
} from "@phosphor-icons/react"

import {
  api,
  trackCoverUrl,
  type PlaylistDetailOut,
  type TrackOut,
} from "~/lib/api"
import { playTrack, toggleTrack, useAudioPlayer } from "~/lib/audio-player"
import { type PlaylistColor } from "~/lib/api"
import {
  playlistCardPalette,
  playlistThemeColors,
  rankCoverColors,
} from "~/lib/playlist-palette"
import { cn } from "~/lib/utils"
import { ArtistCredits } from "~/components/artist-credits"
import { PlaylistDetailSkeleton } from "~/components/loading"
import { PlaylistColorPicker } from "~/components/playlist-color-picker"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "~/components/ui/alert-dialog"
import { Button } from "~/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "~/components/ui/dialog"
import { Input } from "~/components/ui/input"
import { Label } from "~/components/ui/label"
import { Textarea } from "~/components/ui/textarea"

import { FALLBACK_COVER_COLOR } from "~/client/constants.gen"


function isPlaylistDetail(value: unknown): value is PlaylistDetailOut {
  return (
    typeof value === "object" &&
    value != null &&
    "id" in value &&
    "tracks" in value &&
    Array.isArray((value as PlaylistDetailOut).tracks)
  )
}

export default function PlaylistDetailPage() {
  const { playlistId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const player = useAudioPlayer()

  const [playlist, setPlaylist] = useState<PlaylistDetailOut | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [editOpen, setEditOpen] = useState(false)
  const [editTitle, setEditTitle] = useState("")
  const [editDescription, setEditDescription] = useState("")
  const [editColor, setEditColor] = useState<PlaylistColor | null>(null)

  const [deleteOpen, setDeleteOpen] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [catalog, setCatalog] = useState<TrackOut[] | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [searching, setSearching] = useState(false)

  useEffect(() => {
    if (!playlistId) return
    let cancelled = false

    const stateSeed = isPlaylistDetail(
      (location.state as { seed?: unknown } | null)?.seed,
    )
      ? (location.state as { seed: PlaylistDetailOut }).seed
      : null

    if (stateSeed?.id === playlistId) {
      setPlaylist(stateSeed)
      setError(null)
    } else {
      setPlaylist(null)
    }

    void api.v1
      .getPlaylist({ path: { playlist_id: playlistId } })
      .then((result) => {
        if (cancelled) return
        if (result.error || !result.data) {
          setError("Playlist not found")
          setPlaylist(null)
          return
        }
        setError(null)
        setPlaylist(result.data)
      })

    return () => {
      cancelled = true
    }
  }, [playlistId])

  async function reload() {
    if (!playlistId) return
    const result = await api.v1.getPlaylist({
      path: { playlist_id: playlistId },
    })
    if (result.error || !result.data) {
      setError("Playlist not found")
      setPlaylist(null)
      return
    }
    setError(null)
    setPlaylist(result.data)
  }

  const memberIds = useMemo(
    () => new Set(playlist?.tracks.map((track) => track.id) ?? []),
    [playlist],
  )

  const headerPalette = useMemo(() => {
    const theme = playlist?.theme_colors ?? []
    const covers = rankCoverColors(
      playlist?.tracks.map((track) => track.cover_color) ?? [],
    )
    return playlistCardPalette(playlistThemeColors(theme, covers))
  }, [playlist])

  const firstReady = playlist?.tracks.find((track) => track.status === "ready")
  async function persistOrder(nextTracks: TrackOut[]) {
    if (!playlistId) return
    setBusy(true)
    setError(null)
    const { data, error: apiError } = await api.v1.reorderPlaylistTracks({
      path: { playlist_id: playlistId },
      body: { track_ids: nextTracks.map((track) => track.id) },
    })
    setBusy(false)
    if (apiError || !data) {
      setError("Could not reorder tracks")
      await reload()
      return
    }
    setPlaylist(data)
  }

  async function moveTrack(index: number, direction: -1 | 1) {
    if (!playlist) return
    const target = index + direction
    if (target < 0 || target >= playlist.tracks.length) return
    const next = [...playlist.tracks]
    const [row] = next.splice(index, 1)
    next.splice(target, 0, row)
    setPlaylist({ ...playlist, tracks: next })
    await persistOrder(next)
  }

  async function removeTrack(trackId: string) {
    if (!playlistId) return
    setBusy(true)
    setError(null)
    const { data, error: apiError } = await api.v1.removePlaylistTracks({
      path: { playlist_id: playlistId },
      body: { track_ids: [trackId] },
    })
    setBusy(false)
    if (apiError || !data) {
      setError("Could not remove track")
      return
    }
    setPlaylist(data)
  }

  async function saveEdit() {
    if (!playlistId) return
    const clean = editTitle.trim()
    if (!clean) {
      setError("Title is required")
      return
    }
    setBusy(true)
    setError(null)
    const { data, error: apiError } = await api.v1.updatePlaylist({
      path: { playlist_id: playlistId },
      body: {
        title: clean,
        description: editDescription.trim() || null,
        clear_description: !editDescription.trim(),
        ...(editColor ? { color: editColor } : {}),
      },
    })
    setBusy(false)
    if (apiError || !data) {
      setError("Could not update playlist")
      return
    }
    setPlaylist(data)
    setEditOpen(false)
  }

  async function handleDelete() {
    if (!playlistId) return
    setBusy(true)
    setError(null)
    const { error: apiError } = await api.v1.deletePlaylist({
      path: { playlist_id: playlistId },
    })
    setBusy(false)
    if (apiError) {
      setError("Could not delete playlist")
      setDeleteOpen(false)
      return
    }
    void navigate("/playlists")
  }

  async function searchCatalog(nextQuery: string) {
    setSearching(true)
    const result = await api.v1.listTracks({
      query: {
        q: nextQuery.trim() || undefined,
        status: "ready",
        limit: 40,
      },
    })
    setSearching(false)
    if (result.error || !result.data) {
      setCatalog([])
      return
    }
    setCatalog(result.data.items)
  }

  async function addSelected() {
    if (!playlistId || selected.size === 0) return
    setBusy(true)
    setError(null)
    const { data, error: apiError } = await api.v1.addPlaylistTracks({
      path: { playlist_id: playlistId },
      body: { track_ids: [...selected] },
    })
    setBusy(false)
    if (apiError || !data) {
      setError("Could not add tracks")
      return
    }
    setPlaylist(data)
    setAddOpen(false)
    setSelected(new Set())
    setQuery("")
    setCatalog(null)
  }

  if (!playlistId) {
    return <p className="text-destructive text-sm">Missing playlist id</p>
  }

  if (playlist === null && !error) {
    return (
      <div className="flex max-w-4xl flex-col gap-6">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="w-fit"
          render={<Link to="/playlists" />}
        >
          <ArrowLeft className="size-4" />
          Back to playlists
        </Button>
        <PlaylistDetailSkeleton />
      </div>
    )
  }

  if (playlist === null) {
    return (
      <div className="flex max-w-4xl flex-col gap-4">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="w-fit"
          render={<Link to="/playlists" />}
        >
          <ArrowLeft className="size-4" />
          Back to playlists
        </Button>
        <p className="text-destructive text-sm">{error ?? "Playlist not found"}</p>
      </div>
    )
  }

  return (
    <div className="flex max-w-4xl flex-col gap-6">
      <div className="flex flex-col gap-4">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="w-fit"
          render={<Link to="/playlists" />}
        >
          <ArrowLeft className="size-4" />
          Back to playlists
        </Button>

        <div
          className="relative w-full overflow-hidden rounded-2xl"
          style={headerPalette.style}
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 opacity-40"
            style={{
              backgroundImage: `radial-gradient(ellipse 80% 70% at 100% 0%, ${headerPalette.colors[1]}aa 0%, transparent 55%), radial-gradient(ellipse 70% 60% at 0% 100%, ${headerPalette.colors[2]}99 0%, transparent 50%)`,
            }}
          />
          <div className="relative z-[1] flex flex-wrap items-start justify-between gap-4 p-5 sm:p-6">
            <div className="min-w-0 flex-1">
              <h1 className="text-2xl font-medium tracking-tight">
                {playlist.title}
              </h1>
              {playlist.description ? (
                <p
                  className="mt-1 text-sm leading-relaxed"
                  style={{ color: "var(--playlist-fg-muted)" }}
                >
                  {playlist.description}
                </p>
              ) : null}
              <p
                className="mt-1 text-xs"
                style={{ color: "var(--playlist-fg-muted)" }}
              >
                {playlist.tracks.length}{" "}
                {playlist.tracks.length === 1 ? "track" : "tracks"}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={!firstReady || busy}
                className="border-[color:var(--playlist-btn-border)] bg-[color:var(--playlist-btn)] text-inherit hover:bg-[color:var(--playlist-btn-hover)] hover:text-inherit"
                onClick={() => {
                  if (firstReady) void playTrack(firstReady)
                }}
              >
                <Play className="size-4" weight="fill" />
                Play
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                className="border-[color:var(--playlist-btn-border)] bg-[color:var(--playlist-btn)] text-inherit hover:bg-[color:var(--playlist-btn-hover)] hover:text-inherit"
                onClick={() => {
                  setEditTitle(playlist.title)
                  setEditDescription(playlist.description ?? "")
                  setEditColor(
                    (playlist.color as PlaylistColor | null | undefined) ??
                      null,
                  )
                  setEditOpen(true)
                }}
              >
                <PencilSimple className="size-4" />
                Edit
              </Button>
              <Button
                type="button"
                disabled={busy}
                className="border-transparent bg-[color:var(--playlist-solid)] text-[color:var(--playlist-solid-fg)] hover:bg-[color:var(--playlist-solid)] hover:opacity-90 hover:text-[color:var(--playlist-solid-fg)]"
                onClick={() => {
                  setAddOpen(true)
                  setSelected(new Set())
                  setQuery("")
                  void searchCatalog("")
                }}
              >
                <Plus className="size-4" />
                Add tracks
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                className={cn(
                  "border-[color:var(--playlist-btn-border)] bg-[color:var(--playlist-btn)] hover:bg-[color:var(--playlist-btn-hover)]",
                  headerPalette.onDark
                    ? "text-red-200 hover:text-red-100"
                    : "text-red-700 hover:text-red-800",
                )}
                onClick={() => setDeleteOpen(true)}
              >
                <Trash className="size-4" />
                Delete
              </Button>
            </div>
          </div>
        </div>
      </div>

      {error ? <p className="text-destructive text-sm">{error}</p> : null}

      {playlist.tracks.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No tracks yet. Add some from your catalog.
        </p>
      ) : (
        <ul className="flex flex-col gap-0.5">
          {playlist.tracks.map((track, index) => {
            const isActive = player.track?.id === track.id
            const isPlaying = isActive && player.playing
            const canPlay = track.status === "ready"

            return (
              <li key={track.id}>
                <div
                  className={cn(
                    "group flex w-full items-center gap-2 rounded-lg px-2 py-2",
                    canPlay && "hover:bg-muted",
                    isActive && "bg-muted/70",
                  )}
                >
                  <span className="text-muted-foreground w-6 shrink-0 text-center text-xs tabular-nums">
                    {index + 1}
                  </span>
                  <button
                    type="button"
                    className={cn(
                      "flex min-w-0 flex-1 items-center gap-3 text-left",
                      !canPlay && "cursor-default opacity-60",
                    )}
                    disabled={!canPlay || busy}
                    onClick={() => {
                      if (canPlay) void toggleTrack(track)
                    }}
                  >
                    <span className="relative shrink-0">
                      <span
                        className="relative block size-10 overflow-hidden rounded-md bg-muted"
                        style={{
                          backgroundColor: track.cover_color || FALLBACK_COVER_COLOR,
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
                        <ArtistCredits track={track} className="text-sm" />
                      </span>
                    </span>
                  </button>

                  <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                    <Button
                      type="button"
                      size="icon-sm"
                      variant="ghost"
                      disabled={busy || index === 0}
                      aria-label="Move up"
                      onClick={() => void moveTrack(index, -1)}
                    >
                      <ArrowUp className="size-4" />
                    </Button>
                    <Button
                      type="button"
                      size="icon-sm"
                      variant="ghost"
                      disabled={busy || index === playlist.tracks.length - 1}
                      aria-label="Move down"
                      onClick={() => void moveTrack(index, 1)}
                    >
                      <ArrowDown className="size-4" />
                    </Button>
                    <Button
                      type="button"
                      size="icon-sm"
                      variant="ghost"
                      disabled={busy}
                      aria-label={`Remove ${track.title}`}
                      onClick={() => void removeTrack(track.id)}
                    >
                      <Trash className="size-4" />
                    </Button>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit playlist</DialogTitle>
            <DialogDescription>
              Update the title, description, or mood color.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-2">
              <Label htmlFor="edit-playlist-title">Title</Label>
              <Input
                id="edit-playlist-title"
                value={editTitle}
                onChange={(event) => setEditTitle(event.target.value)}
                maxLength={200}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="edit-playlist-description">Description</Label>
              <Textarea
                id="edit-playlist-description"
                value={editDescription}
                onChange={(event) => setEditDescription(event.target.value)}
                maxLength={2000}
                rows={3}
              />
            </div>
            <PlaylistColorPicker
              value={editColor}
              onChange={setEditColor}
              optional
            />
          </div>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" />} disabled={busy}>
              Cancel
            </DialogClose>
            <Button
              type="button"
              disabled={busy || !editTitle.trim()}
              onClick={() => void saveEdit()}
            >
              {busy ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={addOpen}
        onOpenChange={(open) => {
          setAddOpen(open)
          if (!open) {
            setCatalog(null)
            setSelected(new Set())
            setQuery("")
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Add tracks</DialogTitle>
            <DialogDescription>
              Search the catalog and add ready tracks.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <div className="relative">
              <MagnifyingGlass className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2" />
              <Input
                className="pl-9"
                placeholder="Search title or artist"
                value={query}
                onChange={(event) => {
                  const value = event.target.value
                  setQuery(value)
                  void searchCatalog(value)
                }}
              />
            </div>
            <div className="max-h-72 overflow-y-auto rounded-md border">
              {searching && catalog === null ? (
                <p className="text-muted-foreground p-3 text-sm">Searching…</p>
              ) : catalog == null || catalog.length === 0 ? (
                <p className="text-muted-foreground p-3 text-sm">
                  No ready tracks found.
                </p>
              ) : (
                <ul className="flex flex-col">
                  {catalog.map((track) => {
                    const alreadyIn = memberIds.has(track.id)
                    const checked = selected.has(track.id)
                    return (
                      <li key={track.id}>
                        <label
                          className={cn(
                            "hover:bg-muted flex cursor-pointer items-center gap-3 px-3 py-2",
                            alreadyIn && "opacity-50",
                          )}
                        >
                          <input
                            type="checkbox"
                            className="size-4"
                            disabled={alreadyIn || busy}
                            checked={alreadyIn || checked}
                            onChange={() => {
                              if (alreadyIn) return
                              setSelected((prev) => {
                                const next = new Set(prev)
                                if (next.has(track.id)) next.delete(track.id)
                                else next.add(track.id)
                                return next
                              })
                            }}
                          />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium">
                              {track.title}
                            </span>
                            <span className="text-muted-foreground block truncate text-xs">
                              {alreadyIn ? (
                                "Already in playlist"
                              ) : (
                                <ArtistCredits track={track} className="text-xs" />
                              )}
                            </span>
                          </span>
                        </label>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          </div>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" />} disabled={busy}>
              Cancel
            </DialogClose>
            <Button
              type="button"
              disabled={busy || selected.size === 0}
              onClick={() => void addSelected()}
            >
              {busy
                ? "Adding…"
                : `Add${selected.size > 0 ? ` (${selected.size})` : ""}`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete playlist?</AlertDialogTitle>
            <AlertDialogDescription>
              “{playlist.title}” will be permanently deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={busy}
              onClick={(event) => {
                event.preventDefault()
                void handleDelete()
              }}
            >
              {busy ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
