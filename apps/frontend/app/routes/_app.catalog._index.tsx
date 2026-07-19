import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router"
import { Queue } from "@phosphor-icons/react"
import { toast } from "sonner"

import { api, type TrackOut, type TrackStatus } from "~/lib/api"
import {
  CatalogTracksTable,
  type CatalogOrder,
  type CatalogSort,
} from "~/components/catalog-tracks-table"
import { CatalogTableSkeleton } from "~/components/loading"
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
import { Input } from "~/components/ui/input"
import { Label } from "~/components/ui/label"

const PENDING_TRACK: TrackStatus[] = ["uploading", "queued", "indexing"]
const PAGE_SIZE = 50

export default function CatalogTracksPage() {
  const [tracks, setTracks] = useState<TrackOut[] | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [qInput, setQInput] = useState("")
  const [artistInput, setArtistInput] = useState("")
  const [q, setQ] = useState("")
  const [artist, setArtist] = useState("")
  const [sort, setSort] = useState<CatalogSort>("imported_at")
  const [order, setOrder] = useState<CatalogOrder>("desc")
  const [deleting, setDeleting] = useState(false)
  const [deleteIds, setDeleteIds] = useState<string[] | null>(null)

  useEffect(() => {
    const id = window.setTimeout(() => {
      setQ(qInput.trim())
      setPage(0)
    }, 300)
    return () => window.clearTimeout(id)
  }, [qInput])

  useEffect(() => {
    const id = window.setTimeout(() => {
      setArtist(artistInput.trim())
      setPage(0)
    }, 300)
    return () => window.clearTimeout(id)
  }, [artistInput])

  const refresh = useCallback(
    async (nextPage: number) => {
      const tracksResult = await api.v1.listTracks({
        query: {
          q: q || null,
          artist: artist || null,
          sort,
          order,
          limit: PAGE_SIZE,
          offset: nextPage * PAGE_SIZE,
        },
      })
      if (tracksResult.error || !tracksResult.data) {
        toast.error("Could not load tracks")
        return
      }
      setTracks(tracksResult.data.items)
      setTotal(tracksResult.data.total)
      const maxPage = Math.max(
        0,
        Math.ceil(tracksResult.data.total / PAGE_SIZE) - 1,
      )
      if (nextPage > maxPage) {
        setPage(maxPage)
      }
    },
    [artist, order, q, sort],
  )

  useEffect(() => {
    void refresh(page)
  }, [page, refresh])

  useEffect(() => {
    const tracksPending = tracks?.some((track) =>
      PENDING_TRACK.includes(track.status),
    )
    if (!tracksPending) return
    const id = window.setInterval(() => {
      void refresh(page)
    }, 2000)
    return () => window.clearInterval(id)
  }, [tracks, page, refresh])

  function handleSortChange(nextSort: CatalogSort) {
    if (sort === nextSort) {
      setOrder((value) => (value === "asc" ? "desc" : "asc"))
    } else {
      setSort(nextSort)
      setOrder(nextSort === "imported_at" ? "desc" : "asc")
    }
    setPage(0)
  }

  async function handleDelete() {
    if (!deleteIds || deleteIds.length === 0) return
    setDeleting(true)
    const { error: apiError } = await api.v1.deleteTracks({
      body: { track_ids: deleteIds },
    })
    setDeleting(false)
    const count = deleteIds.length
    setDeleteIds(null)
    if (apiError) {
      toast.error(count > 1 ? "Could not delete tracks" : "Could not delete track")
      return
    }
    toast.success(count > 1 ? `Deleted ${count} tracks` : "Track deleted")
    await refresh(page)
  }

  return (
    <div className="flex flex-col gap-6">
      <p className="text-muted-foreground text-sm leading-relaxed">
        Upload and indexing live under{" "}
        <Link
          to="/jobs"
          className="text-foreground relative top-[2.5px] inline-flex items-center gap-1 underline-offset-4 hover:underline"
        >
          <Queue className="size-3.5" />
          Jobs
        </Link>
        .
      </p>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-2">
          <Label htmlFor="catalog-search">Search title</Label>
          <Input
            id="catalog-search"
            value={qInput}
            onChange={(event) => setQInput(event.target.value)}
            placeholder="Search by track name…"
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="catalog-artist">Filter artist</Label>
          <Input
            id="catalog-artist"
            value={artistInput}
            onChange={(event) => setArtistInput(event.target.value)}
            placeholder="Filter by artist…"
          />
        </div>
      </div>

      {tracks === null ? (
        <CatalogTableSkeleton />
      ) : (
        <CatalogTracksTable
          tracks={tracks}
          total={total}
          page={page}
          pageSize={PAGE_SIZE}
          sort={sort}
          order={order}
          onPageChange={setPage}
          onSortChange={handleSortChange}
          onDelete={setDeleteIds}
          onTrackUpdated={(updated) => {
            setTracks((prev) =>
              prev
                ? prev.map((track) =>
                    track.id === updated.id ? updated : track,
                  )
                : prev,
            )
          }}
        />
      )}

      <AlertDialog
        open={deleteIds != null}
        onOpenChange={(open) => {
          if (!open) setDeleteIds(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {deleteIds && deleteIds.length > 1
                ? `Delete ${deleteIds.length} tracks?`
                : "Delete track?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the track
              {deleteIds && deleteIds.length > 1 ? "s" : ""} from your catalog,
              playlists, search index, and graph.
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
