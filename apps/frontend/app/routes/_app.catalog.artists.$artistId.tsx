import { useCallback, useEffect, useState } from "react"
import { Link, useParams } from "react-router"
import { toast } from "sonner"

import { api, artistImageUrl, type ArtistOut, type TrackOut, type TrackStatus } from "~/lib/api"
import {
  CatalogTracksTable,
  type CatalogOrder,
  type CatalogSort,
} from "~/components/catalog-tracks-table"
import {
  ArtistHeaderSkeleton,
  CatalogTableSkeleton,
} from "~/components/loading"
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

const PENDING_TRACK: TrackStatus[] = ["uploading", "queued", "indexing"]
const PAGE_SIZE = 50

export default function CatalogArtistDetailPage() {
  const { artistId } = useParams()
  const [artist, setArtist] = useState<ArtistOut | null>(null)
  const [tracks, setTracks] = useState<TrackOut[] | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [sort, setSort] = useState<CatalogSort>("imported_at")
  const [order, setOrder] = useState<CatalogOrder>("desc")
  const [deleting, setDeleting] = useState(false)
  const [deleteIds, setDeleteIds] = useState<string[] | null>(null)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    if (!artistId) return
    void (async () => {
      const result = await api.v1.getArtist({
        path: { artist_id: artistId },
      })
      if (result.error || !result.data) {
        setMissing(true)
        setArtist(null)
        return
      }
      setMissing(false)
      setArtist(result.data)
    })()
  }, [artistId])

  const refresh = useCallback(
    async (nextPage: number) => {
      if (!artistId) return
      const tracksResult = await api.v1.listTracks({
        query: {
          artist_id: artistId,
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
      if (nextPage > maxPage) setPage(maxPage)
    },
    [artistId, order, sort],
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

  if (missing) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-sm">Artist not found.</p>
        <Link to="/catalog/artists" className="text-sm underline-offset-4 hover:underline">
          Back to artists
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <Link
          to="/catalog/artists"
          className="text-muted-foreground w-fit text-sm underline-offset-4 hover:underline"
        >
          Artists
        </Link>
        <div className="flex items-center gap-3">
          {artist ? (
            <>
              <span className="bg-muted relative size-14 shrink-0 overflow-hidden rounded-full">
                {artist.has_image ? (
                  <img
                    src={artistImageUrl(artist.id)}
                    alt=""
                    className="absolute inset-0 size-full object-cover"
                  />
                ) : null}
              </span>
              <div className="min-w-0">
                <h2 className="truncate text-xl font-medium tracking-tight">
                  {artist.name}
                </h2>
                <p className="text-muted-foreground text-sm">
                  {artist.track_count ?? total} track
                  {(artist.track_count ?? total) === 1 ? "" : "s"}
                  {" · "}
                  added{" "}
                  {new Date(artist.created_at).toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                  })}
                </p>
              </div>
            </>
          ) : (
            <ArtistHeaderSkeleton />
          )}
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
