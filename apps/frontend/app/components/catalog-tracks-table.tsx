import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router"
import {
  ArrowDown,
  ArrowUp,
  DotsThree,
  Graph,
  PencilSimple,
  Pause,
  Play,
  Trash,
} from "@phosphor-icons/react"
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type RowSelectionState,
} from "@tanstack/react-table"

import { trackCoverUrl, type TrackOut, type TrackStatus } from "~/lib/api"
import { formatTime, toggleTrack, useAudioPlayer } from "~/lib/audio-player"
import { ArtistCredits } from "~/components/artist-credits"
import { EditTrackDialog } from "~/components/edit-track-dialog"
import { Badge } from "~/components/ui/badge"
import { Button } from "~/components/ui/button"
import { Checkbox } from "~/components/ui/checkbox"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "~/components/ui/dropdown-menu"
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

import { FALLBACK_COVER_COLOR } from "~/client/constants.gen"


export type CatalogSort = "imported_at" | "duration" | "title" | "artist"
export type CatalogOrder = "asc" | "desc"

function statusVariant(status: string) {
  if (status === "ready" || status === "complete") return "default" as const
  if (status === "failed") return "destructive" as const
  return "secondary" as const
}

function formatUploaded(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function TrackArt({ track }: { track: TrackOut }) {
  return (
    <div
      className="relative size-10 shrink-0 overflow-hidden rounded-md bg-muted"
      style={{ backgroundColor: track.cover_color || FALLBACK_COVER_COLOR }}
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

function SortHeader({
  label,
  active,
  order,
  onClick,
}: {
  label: string
  active: boolean
  order: CatalogOrder
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center gap-1 font-medium hover:text-foreground",
        active ? "text-foreground" : "text-muted-foreground",
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

type CatalogTracksTableProps = {
  tracks: TrackOut[]
  total: number
  page: number
  pageSize: number
  sort: CatalogSort
  order: CatalogOrder
  onPageChange: (page: number) => void
  onSortChange: (sort: CatalogSort) => void
  onDelete: (trackIds: string[]) => void
  onTrackUpdated?: (track: TrackOut) => void
}

export function CatalogTracksTable({
  tracks,
  total,
  page,
  pageSize,
  sort,
  order,
  onPageChange,
  onSortChange,
  onDelete,
  onTrackUpdated,
}: CatalogTracksTableProps) {
  const player = useAudioPlayer()
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})
  const [editTrack, setEditTrack] = useState<TrackOut | null>(null)

  const pageCount = Math.max(1, Math.ceil(total / pageSize))

  const columns = useMemo<ColumnDef<TrackOut>[]>(
    () => [
      {
        id: "select",
        header: ({ table }) => (
          <Checkbox
            checked={table.getIsAllPageRowsSelected()}
            indeterminate={
              table.getIsSomePageRowsSelected() &&
              !table.getIsAllPageRowsSelected()
            }
            onCheckedChange={(checked) =>
              table.toggleAllPageRowsSelected(checked)
            }
            aria-label="Select all"
            onClick={(event) => event.stopPropagation()}
          />
        ),
        cell: ({ row }) => (
          <Checkbox
            checked={row.getIsSelected()}
            onCheckedChange={(checked) => row.toggleSelected(checked)}
            aria-label="Select row"
            onClick={(event) => event.stopPropagation()}
          />
        ),
        size: 32,
      },
      {
        id: "track",
        header: () => (
          <SortHeader
            label="Track"
            active={sort === "title"}
            order={order}
            onClick={() => onSortChange("title")}
          />
        ),
        cell: ({ row }) => {
          const track = row.original
          const isActive = player.track?.id === track.id
          const isPlaying = isActive && player.playing
          const canPlay = track.status === "ready"
          return (
            <div className="flex min-w-0 items-center gap-3">
              <span className="relative shrink-0">
                <TrackArt track={track} />
                {canPlay ? (
                  <span
                    className={cn(
                      "absolute inset-0 flex items-center justify-center rounded-md bg-black/45 text-white opacity-0 transition-opacity",
                      "group-hover/row:opacity-100",
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
                <span className="block truncate font-medium">{track.title}</span>
                <span className="text-muted-foreground block truncate text-sm">
                  <ArtistCredits track={track} className="text-sm" />
                </span>
                {track.status === "failed" && track.error_message ? (
                  <span className="text-destructive mt-0.5 block truncate text-xs">
                    {track.error_message}
                  </span>
                ) : null}
              </span>
              {track.status !== "ready" ? (
                <Badge variant={statusVariant(track.status as TrackStatus)}>
                  {track.status}
                </Badge>
              ) : null}
            </div>
          )
        },
      },
      {
        id: "uploaded",
        header: () => (
          <SortHeader
            label="Uploaded"
            active={sort === "imported_at"}
            order={order}
            onClick={() => onSortChange("imported_at")}
          />
        ),
        cell: ({ row }) => (
          <span className="text-muted-foreground tabular-nums">
            {formatUploaded(row.original.imported_at)}
          </span>
        ),
        size: 110,
      },
      {
        id: "duration",
        header: () => (
          <SortHeader
            label="Duration"
            active={sort === "duration"}
            order={order}
            onClick={() => onSortChange("duration")}
          />
        ),
        cell: ({ row }) => {
          const seconds = row.original.duration_s
          return (
            <span className="text-muted-foreground tabular-nums">
              {seconds != null && seconds > 0 ? formatTime(seconds) : "—"}
            </span>
          )
        },
        size: 80,
      },
      {
        id: "actions",
        header: () => <span className="sr-only">Actions</span>,
        cell: ({ row }) => {
          const track = row.original
          return (
            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <Button
                    type="button"
                    size="icon-sm"
                    variant="ghost"
                    className="opacity-0 group-hover/row:opacity-100 focus-visible:opacity-100 data-popup-open:opacity-100"
                    aria-label="Track actions"
                    onClick={(event) => event.stopPropagation()}
                  />
                }
              >
                <DotsThree weight="bold" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="min-w-40">
                <DropdownMenuItem onClick={() => setEditTrack(track)}>
                  <PencilSimple weight="regular" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem
                  render={<Link to={`/graph?focus=${track.id}`} />}
                >
                  <Graph weight="regular" />
                  Go to graph
                </DropdownMenuItem>
                <DropdownMenuItem
                  variant="destructive"
                  onClick={() => onDelete([track.id])}
                >
                  <Trash weight="regular" />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )
        },
        size: 40,
      },
    ],
    [onDelete, onSortChange, order, player.playing, player.track?.id, sort],
  )

  const table = useReactTable({
    data: tracks,
    columns,
    state: { rowSelection },
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (row) => row.id,
    manualPagination: true,
    pageCount,
    rowCount: total,
  })

  useEffect(() => {
    setRowSelection({})
  }, [page])

  useEffect(() => {
    const ids = new Set(tracks.map((track) => track.id))
    setRowSelection((prev) => {
      let changed = false
      const next: RowSelectionState = {}
      for (const [id, selected] of Object.entries(prev)) {
        if (selected && ids.has(id)) next[id] = true
        else if (selected) changed = true
      }
      return changed || Object.keys(next).length !== Object.keys(prev).length
        ? next
        : prev
    })
  }, [tracks])

  const selectedIds = Object.keys(rowSelection).filter((id) => rowSelection[id])

  return (
    <div className="flex flex-col gap-3">
      {selectedIds.length > 0 ? (
        <div className="flex items-center justify-between gap-3 rounded-lg border bg-muted/40 px-3 py-2">
          <p className="text-sm">{selectedIds.length} selected</p>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={() => onDelete(selectedIds)}
          >
            Delete {selectedIds.length}
          </Button>
        </div>
      ) : null}

      <div className="overflow-hidden rounded-lg border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="hover:bg-transparent">
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    style={
                      header.column.getSize() !== 150
                        ? { width: header.column.getSize() }
                        : undefined
                    }
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="text-muted-foreground h-24 text-center"
                >
                  No tracks found.
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => {
                const track = row.original
                const canPlay = track.status === "ready"
                const isActive = player.track?.id === track.id
                return (
                  <TableRow
                    key={row.id}
                    data-state={row.getIsSelected() ? "selected" : undefined}
                    className={cn(
                      "group/row",
                      canPlay && "cursor-pointer",
                      isActive && "bg-muted/70",
                    )}
                    onClick={(event) => {
                      if (!canPlay) return
                      const target = event.target as HTMLElement
                      if (
                        target.closest(
                          '[data-slot="checkbox"], [data-slot="dropdown-menu-trigger"], button, a, input',
                        )
                      ) {
                        return
                      }
                      void toggleTrack(track)
                    }}
                  >
                    {row.getVisibleCells().map((cell) => {
                      const interactive =
                        cell.column.id === "select" ||
                        cell.column.id === "actions"
                      return (
                        <TableCell
                          key={cell.id}
                          onClick={
                            interactive
                              ? (event) => event.stopPropagation()
                              : undefined
                          }
                          onPointerDown={
                            interactive
                              ? (event) => event.stopPropagation()
                              : undefined
                          }
                        >
                          {flexRender(
                            cell.column.columnDef.cell,
                            cell.getContext(),
                          )}
                        </TableCell>
                      )
                    })}
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-muted-foreground text-sm">
          {total === 0
            ? "0 tracks"
            : `${page * pageSize + 1}–${Math.min((page + 1) * pageSize, total)} of ${total}`}
        </p>
        <Pagination className="mx-0 w-auto justify-start sm:justify-end">
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious
                disabled={page <= 0}
                onClick={() => onPageChange(page - 1)}
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
                onClick={() => onPageChange(page + 1)}
              />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      </div>

      <EditTrackDialog
        track={editTrack}
        open={editTrack != null}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setEditTrack(null)
        }}
        onSaved={(updated) => {
          onTrackUpdated?.(updated)
          setEditTrack(null)
        }}
      />
    </div>
  )
}
