import { useCallback, useEffect, useState } from "react"
import { Link } from "react-router"
import { ArrowDown, ArrowUp } from "@phosphor-icons/react"
import { toast } from "sonner"

import { api, artistImageUrl, type ArtistOut } from "~/lib/api"
import { ArtistsTableSkeleton } from "~/components/loading"
import { Input } from "~/components/ui/input"
import { Label } from "~/components/ui/label"
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "~/components/ui/pagination"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "~/components/ui/table"
import { cn } from "~/lib/utils"

const PAGE_SIZE = 50

type ArtistSort = "name" | "track_count" | "created_at"
type ArtistOrder = "asc" | "desc"

function formatCreated(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function SortHeader({
  label,
  active,
  order,
  onClick,
  className,
}: {
  label: string
  active: boolean
  order: ArtistOrder
  onClick: () => void
  className?: string
}) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center gap-1 font-medium hover:text-foreground",
        active ? "text-foreground" : "text-muted-foreground",
        className,
      )}
      onClick={onClick}
    >
      {label}
      {active ? (
        order === "asc" ? (
          <ArrowUp className="size-3.5" />
        ) : (
          <ArrowDown className="size-3.5" />
        )
      ) : null}
    </button>
  )
}

export default function CatalogArtistsPage() {
  const [artists, setArtists] = useState<ArtistOut[] | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [qInput, setQInput] = useState("")
  const [q, setQ] = useState("")
  const [sort, setSort] = useState<ArtistSort>("name")
  const [order, setOrder] = useState<ArtistOrder>("asc")

  useEffect(() => {
    const id = window.setTimeout(() => {
      setQ(qInput.trim())
      setPage(0)
    }, 300)
    return () => window.clearTimeout(id)
  }, [qInput])

  const refresh = useCallback(
    async (nextPage: number) => {
      const result = await api.v1.listArtists({
        query: {
          q: q || null,
          sort,
          order,
          limit: PAGE_SIZE,
          offset: nextPage * PAGE_SIZE,
        },
      })
      if (result.error || !result.data) {
        toast.error("Could not load artists")
        return
      }
      setArtists(result.data.items)
      setTotal(result.data.total)
      const maxPage = Math.max(0, Math.ceil(result.data.total / PAGE_SIZE) - 1)
      if (nextPage > maxPage) setPage(maxPage)
    },
    [order, q, sort],
  )

  useEffect(() => {
    void refresh(page)
  }, [page, refresh])

  function handleSortChange(nextSort: ArtistSort) {
    if (sort === nextSort) {
      setOrder((value) => (value === "asc" ? "desc" : "asc"))
    } else {
      setSort(nextSort)
      setOrder(nextSort === "name" ? "asc" : "desc")
    }
    setPage(0)
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Label htmlFor="artists-search">Search artists</Label>
        <Input
          id="artists-search"
          value={qInput}
          onChange={(event) => setQInput(event.target.value)}
          placeholder="Search by name…"
        />
      </div>

      {artists === null ? (
        <ArtistsTableSkeleton />
      ) : (
        <>
          <div className="overflow-hidden rounded-xl border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>
                    <SortHeader
                      label="Artist"
                      active={sort === "name"}
                      order={order}
                      onClick={() => handleSortChange("name")}
                    />
                  </TableHead>
                  <TableHead className="w-28 text-right">
                    <SortHeader
                      label="Tracks"
                      active={sort === "track_count"}
                      order={order}
                      onClick={() => handleSortChange("track_count")}
                      className="ml-auto"
                    />
                  </TableHead>
                  <TableHead className="w-36">
                    <SortHeader
                      label="Created"
                      active={sort === "created_at"}
                      order={order}
                      onClick={() => handleSortChange("created_at")}
                    />
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {artists.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={3} className="text-muted-foreground">
                      No artists found.
                    </TableCell>
                  </TableRow>
                ) : (
                  artists.map((artist) => (
                    <TableRow key={artist.id}>
                      <TableCell>
                        <Link
                          to={`/catalog/artists/${artist.id}`}
                          className="flex min-w-0 items-center gap-3 font-medium hover:underline"
                        >
                          <span className="bg-muted relative size-9 shrink-0 overflow-hidden rounded-full">
                            {artist.has_image ? (
                              <img
                                src={artistImageUrl(artist.id)}
                                alt=""
                                className="absolute inset-0 size-full object-cover"
                              />
                            ) : null}
                          </span>
                          <span className="truncate">{artist.name}</span>
                        </Link>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-right tabular-nums">
                        {artist.track_count ?? 0}
                      </TableCell>
                      <TableCell className="text-muted-foreground tabular-nums">
                        {formatCreated(artist.created_at)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-muted-foreground text-sm">
              {total === 0
                ? "0 artists"
                : `${page * PAGE_SIZE + 1}–${Math.min((page + 1) * PAGE_SIZE, total)} of ${total}`}
            </p>
            <Pagination className="mx-0 w-auto justify-start sm:justify-end">
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    disabled={page <= 0}
                    onClick={() => setPage(page - 1)}
                  />
                </PaginationItem>
                <PaginationItem>
                  <span className="text-muted-foreground px-2 text-sm tabular-nums">
                    {page + 1} / {pageCount}
                  </span>
                </PaginationItem>
                <PaginationItem>
                  <PaginationNext
                    disabled={page + 1 >= pageCount}
                    onClick={() => setPage(page + 1)}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </div>
        </>
      )}
    </div>
  )
}
