import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router"
import { Playlist, Plus, Trash } from "@phosphor-icons/react"

import { ChatPrompter } from "~/components/chat-prompter"
import { api, type PlaylistSummaryOut } from "~/lib/api"
import { cn } from "~/lib/utils"
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

const PLAYLIST_IDEAS = [
  {
    label: "Deep focus",
    hint: "Soft electronic · no vocals",
    prompt:
      "Create a focus playlist: soft electronic, no vocals, about 15 tracks",
  },
  {
    label: "Evening wind-down",
    hint: "Warm · low energy",
    prompt: "Build a warm evening wind-down mix from the catalog",
  },
  {
    label: "Workout push",
    hint: "High energy · similar tracks",
    prompt:
      "Make a high-energy workout playlist with similar tracks to whatever hits hardest",
  },
  {
    label: "Rainy day",
    hint: "Melancholic · instrumental",
    prompt: "Playlist of melancholic instrumentals for rainy days",
  },
] as const

function formatUpdated(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

export default function PlaylistsIndexPage() {
  const navigate = useNavigate()
  const [playlists, setPlaylists] = useState<PlaylistSummaryOut[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [prompt, setPrompt] = useState("")
  const [asking, setAsking] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [creating, setCreating] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<PlaylistSummaryOut | null>(
    null,
  )
  const [deleting, setDeleting] = useState(false)

  async function refresh() {
    const result = await api.v1.listPlaylists()
    if (result.error || !result.data) {
      setError("Could not load playlists")
      return
    }
    setError(null)
    setPlaylists(result.data)
  }

  useEffect(() => {
    void refresh()
  }, [])

  async function startPlaylistChat(message: string) {
    setAsking(true)
    setError(null)
    const { data, error: apiError } = await api.v1.createChat({
      body: { message },
    })
    setAsking(false)
    if (apiError || !data) {
      setError("Could not start chat")
      return
    }
    void navigate(`/chat/${data.id}`, { state: { seed: data } })
  }

  async function handleCreate() {
    const clean = title.trim()
    if (!clean) {
      setError("Title is required")
      return
    }
    setCreating(true)
    setError(null)
    const { data, error: apiError } = await api.v1.createPlaylist({
      body: {
        title: clean,
        description: description.trim() || null,
      },
    })
    setCreating(false)
    if (apiError || !data) {
      setError("Could not create playlist")
      return
    }
    setCreateOpen(false)
    setTitle("")
    setDescription("")
    void navigate(`/playlists/${data.id}`, {
      state: { seed: data },
    })
  }

  async function handleDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    setError(null)
    const { error: apiError } = await api.v1.deletePlaylist({
      path: { playlist_id: deleteTarget.id },
    })
    setDeleting(false)
    setDeleteTarget(null)
    if (apiError) {
      setError("Could not delete playlist")
      return
    }
    await refresh()
  }

  const hasPlaylists = (playlists?.length ?? 0) > 0

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-12 pb-8">
      <section
        className={cn(
          "relative isolate flex flex-col items-center gap-6 pt-6 text-center sm:pt-10",
          !hasPlaylists && "min-h-[52vh] justify-center",
        )}
      >
        <div
          className="greeting-glow pointer-events-none absolute inset-x-[-20%] top-[28%] bottom-[-20%] -z-10 opacity-80"
          aria-hidden
        >
          <span className="greeting-glow-blob greeting-glow-blob--warm" />
          <span className="greeting-glow-blob greeting-glow-blob--rose" />
          <span className="greeting-glow-blob greeting-glow-blob--cool" />
        </div>

        <div className="relative flex max-w-lg flex-col items-center gap-3">
          <h1 className="text-3xl font-medium tracking-tight sm:text-4xl">
            Describe a vibe.
          </h1>
          <p className="text-muted-foreground text-sm leading-relaxed">
            Chat searches your catalog and builds a private list.
          </p>
        </div>

        <div className="relative w-full max-w-xl">
          <ChatPrompter
            className="w-full bg-background/85 backdrop-blur-sm"
            placeholder="Soft electronic for late focus…"
            disabled={asking}
            autoFocus={!hasPlaylists}
            value={prompt}
            onValueChange={setPrompt}
            onSubmit={(message) => startPlaylistChat(message)}
          />
        </div>

        <div className="relative grid w-full max-w-xl grid-cols-1 gap-2 sm:grid-cols-2">
          {PLAYLIST_IDEAS.map((idea) => {
            const active = prompt === idea.prompt
            return (
              <button
                key={idea.label}
                type="button"
                disabled={asking}
                onClick={() => setPrompt(idea.prompt)}
                className={cn(
                  "rounded-xl border px-4 py-3 text-left transition-[background-color,border-color,transform] duration-200",
                  "hover:bg-background/80 hover:border-foreground/20 active:scale-[0.99]",
                  "bg-background/55 backdrop-blur-sm disabled:opacity-50",
                  active && "border-foreground/30 bg-background shadow-sm",
                )}
              >
                <span className="block text-sm font-medium tracking-tight">
                  {idea.label}
                </span>
                <span className="text-muted-foreground mt-0.5 block text-xs">
                  {idea.hint}
                </span>
              </button>
            )
          })}
        </div>

        <button
          type="button"
          disabled={asking}
          onClick={() => setCreateOpen(true)}
          className="text-muted-foreground hover:text-foreground relative inline-flex items-center gap-1.5 text-xs transition-colors disabled:opacity-50"
        >
          <Plus className="size-3.5" />
          Or start a blank playlist
        </button>

        {error ? (
          <p className="text-destructive relative text-sm">{error}</p>
        ) : null}
      </section>

      <section className="flex flex-col gap-4">
        <div className="flex items-end justify-between gap-3">
          <h2 className="text-sm font-medium tracking-tight">Your library</h2>
          {hasPlaylists ? (
            <span className="text-muted-foreground text-xs tabular-nums">
              {playlists!.length}{" "}
              {playlists!.length === 1 ? "playlist" : "playlists"}
            </span>
          ) : null}
        </div>

        {playlists === null ? (
          <p className="text-muted-foreground text-sm">Loading…</p>
        ) : playlists.length === 0 ? (
          <div className="text-muted-foreground flex flex-col items-center gap-3 rounded-2xl border border-dashed px-6 py-10 text-center">
            <Playlist className="size-7 opacity-40" weight="duotone" />
            <div className="flex max-w-sm flex-col gap-1">
              <p className="text-foreground text-sm font-medium">
                No playlists yet
              </p>
              <p className="text-xs leading-relaxed">
                Pick an idea above, or describe something of your own.
              </p>
            </div>
          </div>
        ) : (
          <ul className="divide-border flex flex-col divide-y overflow-hidden rounded-2xl border">
            {playlists.map((playlist) => (
              <li key={playlist.id} className="bg-background/70">
                <div className="group hover:bg-muted/50 flex items-center gap-3 px-4 py-3 transition-colors">
                  <Link
                    to={`/playlists/${playlist.id}`}
                    className="min-w-0 flex-1 text-left"
                  >
                    <span className="block truncate font-medium tracking-tight">
                      {playlist.title}
                    </span>
                    <span className="text-muted-foreground mt-0.5 block truncate text-xs">
                      {playlist.track_count}{" "}
                      {playlist.track_count === 1 ? "track" : "tracks"}
                      {" · "}
                      Updated {formatUpdated(playlist.updated_at)}
                    </span>
                  </Link>
                  <Button
                    type="button"
                    size="icon-sm"
                    variant="ghost"
                    className="text-muted-foreground opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                    aria-label={`Delete ${playlist.title}`}
                    onClick={() => setDeleteTarget(playlist)}
                  >
                    <Trash className="size-4" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          setCreateOpen(open)
          if (!open) {
            setTitle("")
            setDescription("")
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Blank playlist</DialogTitle>
            <DialogDescription>
              Give it a name. You can add tracks on the next screen.
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-2">
              <Label htmlFor="playlist-title">Title</Label>
              <Input
                id="playlist-title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                maxLength={200}
                autoFocus
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault()
                    void handleCreate()
                  }
                }}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="playlist-description">Description</Label>
              <Textarea
                id="playlist-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                maxLength={2000}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" />} disabled={creating}>
              Cancel
            </DialogClose>
            <Button
              type="button"
              disabled={creating || !title.trim()}
              onClick={() => void handleCreate()}
            >
              {creating ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={deleteTarget != null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete playlist?</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget
                ? `“${deleteTarget.title}” will be permanently deleted.`
                : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deleting}
              onClick={(event) => {
                event.preventDefault()
                void handleDelete()
              }}
            >
              {deleting ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
