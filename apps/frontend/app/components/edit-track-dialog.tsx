import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Plus, X } from "@phosphor-icons/react"
import { toast } from "sonner"

import {
  api,
  trackCoverUrl,
  type ArtistOut,
  type ArtistRefOut,
  type TrackOut,
} from "~/lib/api"
import { Button } from "~/components/ui/button"
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "~/components/ui/combobox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "~/components/ui/dialog"
import { Input } from "~/components/ui/input"
import { Label } from "~/components/ui/label"
import {
  ALLOWED_IMAGE_MIME_TYPES,
  FALLBACK_COVER_COLOR,
} from "~/client/constants.gen"

const ACCEPT_IMAGE = ALLOWED_IMAGE_MIME_TYPES.join(",")

type EditTrackDialogProps = {
  track: TrackOut | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: (track: TrackOut) => void
}

function artistLabel(artist: ArtistRefOut | ArtistOut) {
  return artist.name
}

export function EditTrackDialog({
  track,
  open,
  onOpenChange,
  onSaved,
}: EditTrackDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [title, setTitle] = useState("")
  const [selected, setSelected] = useState<ArtistRefOut[]>([])
  const [coverFile, setCoverFile] = useState<File | null>(null)
  const [coverPreview, setCoverPreview] = useState<string | null>(null)
  const [artistQuery, setArtistQuery] = useState("")
  const [artistOptions, setArtistOptions] = useState<ArtistOut[]>([])
  const [artistLoading, setArtistLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [newArtistName, setNewArtistName] = useState("")
  const [creating, setCreating] = useState(false)
  const searchTimer = useRef<number | null>(null)

  useEffect(() => {
    if (!open || !track) return
    setTitle(track.title)
    setSelected(track.artists ?? [])
    setCoverFile(null)
    setCoverPreview(null)
    setArtistQuery("")
    setArtistOptions([])
    setCreateOpen(false)
    setNewArtistName("")
  }, [open, track])

  useEffect(() => {
    if (!coverFile) {
      setCoverPreview(null)
      return
    }
    const url = URL.createObjectURL(coverFile)
    setCoverPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [coverFile])

  const fetchArtists = useCallback(async (q: string) => {
    setArtistLoading(true)
    const result = await api.v1.listArtists({
      query: { q: q || null, limit: 20 },
    })
    setArtistLoading(false)
    if (result.error || !result.data) {
      setArtistOptions([])
      return
    }
    setArtistOptions(result.data.items)
  }, [])

  const scheduleSearch = useCallback(
    (value: string) => {
      setArtistQuery(value)
      if (searchTimer.current != null) window.clearTimeout(searchTimer.current)
      searchTimer.current = window.setTimeout(() => {
        void fetchArtists(value.trim())
      }, 200)
    },
    [fetchArtists],
  )

  const availableOptions = useMemo(() => {
    const selectedIds = new Set(selected.map((artist) => artist.id))
    return artistOptions.filter((artist) => !selectedIds.has(artist.id))
  }, [artistOptions, selected])

  const addArtist = (artist: ArtistRefOut | ArtistOut | null) => {
    if (!artist) return
    setSelected((prev) => {
      if (prev.some((item) => item.id === artist.id)) return prev
      return [...prev, { id: artist.id, name: artist.name }]
    })
    setArtistQuery("")
  }

  const removeArtist = (artistId: string) => {
    setSelected((prev) => prev.filter((artist) => artist.id !== artistId))
  }

  const handleCreateArtist = async () => {
    const name = newArtistName.trim()
    if (!name) {
      toast.error("Artist name required")
      return
    }
    setCreating(true)
    const result = await api.v1.createArtist({ body: { name } })
    setCreating(false)
    if (result.error || !result.data) {
      const detail =
        typeof result.error === "object" &&
        result.error &&
        "detail" in result.error
          ? String((result.error as { detail?: unknown }).detail)
          : null
      toast.error(detail || "Could not create artist")
      return
    }
    toast.success(`Created ${result.data.name}`)
    addArtist(result.data)
    setCreateOpen(false)
    setNewArtistName("")
  }

  const handleSave = async () => {
    if (!track) return
    const nextTitle = title.trim()
    if (!nextTitle) {
      toast.error("Title required")
      return
    }
    setSaving(true)
    let updated: TrackOut | null = null
    const patch = await api.v1.updateTrack({
      path: { track_id: track.id },
      body: {
        title: nextTitle,
        artist_ids: selected.map((artist) => artist.id),
      },
    })
    if (patch.error || !patch.data) {
      setSaving(false)
      toast.error("Could not save track")
      return
    }
    updated = patch.data
    if (coverFile) {
      const cover = await api.v1.updateTrackCover({
        path: { track_id: track.id },
        body: { file: coverFile },
      })
      if (cover.error || !cover.data) {
        setSaving(false)
        toast.error("Track saved, but cover upload failed")
        onSaved(updated)
        onOpenChange(false)
        return
      }
      updated = cover.data
    }
    setSaving(false)
    toast.success("Track updated")
    onSaved(updated)
    onOpenChange(false)
  }

  const previewSrc =
    coverPreview ||
    (track?.has_cover ? trackCoverUrl(track.id) : null)

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-2xl" showCloseButton>
          <DialogHeader>
            <DialogTitle>Edit track</DialogTitle>
            <DialogDescription>
              Update cover art, title, and credited artists.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-6 sm:grid-cols-[11rem_1fr]">
            <div className="flex flex-col gap-3">
              <div
                className="relative aspect-square w-full overflow-hidden rounded-lg bg-muted"
                style={{
                  backgroundColor: track?.cover_color || FALLBACK_COVER_COLOR,
                }}
              >
                {previewSrc ? (
                  <img
                    src={previewSrc}
                    alt=""
                    className="absolute inset-0 size-full object-cover"
                  />
                ) : null}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPT_IMAGE}
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null
                  setCoverFile(file)
                }}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
              >
                {track?.has_cover || coverFile ? "Replace cover" : "Add cover"}
              </Button>
            </div>

            <div className="flex min-w-0 flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="edit-track-title">Title</Label>
                <Input
                  id="edit-track-title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  maxLength={512}
                />
              </div>

              <div className="flex flex-col gap-2">
                <Label>Artists</Label>
                {selected.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {selected.map((artist) => (
                      <span
                        key={artist.id}
                        className="bg-secondary text-secondary-foreground inline-flex max-w-full items-center gap-1 rounded-md px-2 py-1 text-xs"
                      >
                        <span className="truncate">{artist.name}</span>
                        <button
                          type="button"
                          className="text-muted-foreground hover:text-foreground shrink-0"
                          aria-label={`Remove ${artist.name}`}
                          onClick={() => removeArtist(artist.id)}
                        >
                          <X className="size-3.5" />
                        </button>
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted-foreground text-xs">
                    No artists assigned yet.
                  </p>
                )}

                <Combobox
                  items={availableOptions}
                  value={null}
                  onValueChange={(artist) => addArtist(artist)}
                  onInputValueChange={scheduleSearch}
                  onOpenChange={(nextOpen) => {
                    if (nextOpen && artistOptions.length === 0) {
                      void fetchArtists(artistQuery.trim())
                    }
                  }}
                  itemToStringLabel={artistLabel}
                  isItemEqualToValue={(item, value) => item.id === value.id}
                  filter={null}
                  inputValue={artistQuery}
                >
                  <ComboboxInput
                    placeholder="Search artists…"
                    className="w-full"
                  />
                  <ComboboxContent className="z-[70]">
                    <button
                      type="button"
                      className="hover:bg-accent flex w-full items-center gap-2 px-2 py-1.5 text-left text-sm"
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => {
                        setNewArtistName(artistQuery.trim())
                        setCreateOpen(true)
                      }}
                    >
                      <Plus className="size-4 shrink-0" />
                      Add new artist
                      {artistQuery.trim() ? (
                        <span className="text-muted-foreground truncate">
                          “{artistQuery.trim()}”
                        </span>
                      ) : null}
                    </button>
                    <ComboboxEmpty>
                      {artistLoading ? "Searching…" : "No artists found."}
                    </ComboboxEmpty>
                    <ComboboxList>
                      {(artist: ArtistOut) => (
                        <ComboboxItem key={artist.id} value={artist}>
                          {artist.name}
                        </ComboboxItem>
                      )}
                    </ComboboxList>
                  </ComboboxContent>
                </Combobox>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button type="button" onClick={() => void handleSave()} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="sm:max-w-md" showCloseButton>
          <DialogHeader>
            <DialogTitle>Add artist</DialogTitle>
            <DialogDescription>
              Create a new artist and assign them to this track.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            <Label htmlFor="new-artist-name">Name</Label>
            <Input
              id="new-artist-name"
              value={newArtistName}
              onChange={(event) => setNewArtistName(event.target.value)}
              maxLength={512}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setCreateOpen(false)}
              disabled={creating}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => void handleCreateArtist()}
              disabled={creating}
            >
              {creating ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
