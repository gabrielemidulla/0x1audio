import { Spinner } from "~/components/ui/spinner"
import { Skeleton } from "~/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "~/components/ui/table"
import { cn } from "~/lib/utils"

/** Full-viewport centered spinner (auth gates, hydrate, etc.). */
export function FullPageSpinner({ className }: { className?: string }) {
  return (
    <main
      className={cn(
        "flex min-h-svh items-center justify-center p-6",
        className,
      )}
    >
      <Spinner className="text-muted-foreground size-8" />
    </main>
  )
}

/** Centered spinner for the current dashboard view / panel. */
export function ViewSpinner({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex min-h-48 flex-1 items-center justify-center py-12",
        className,
      )}
      role="status"
      aria-label="Loading"
    >
      <Spinner className="text-muted-foreground size-6" />
    </div>
  )
}

export function CatalogTableSkeleton({
  rows = 8,
  columns = 6,
}: {
  rows?: number
  columns?: number
}) {
  return (
    <div className="overflow-hidden rounded-xl border">
      <Table>
        <TableHeader>
          <TableRow>
            {Array.from({ length: columns }, (_, i) => (
              <TableHead key={i}>
                <Skeleton className="h-4 w-16" />
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {Array.from({ length: rows }, (_, row) => (
            <TableRow key={row}>
              {Array.from({ length: columns }, (_, col) => (
                <TableCell key={col}>
                  {col === 0 ? (
                    <div className="flex items-center gap-3">
                      <Skeleton className="size-10 shrink-0 rounded-md" />
                      <Skeleton className="h-4 w-32" />
                    </div>
                  ) : (
                    <Skeleton
                      className={cn(
                        "h-4",
                        col === 1 ? "w-24" : col === columns - 1 ? "w-12" : "w-16",
                      )}
                    />
                  )}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export function ArtistsTableSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div className="overflow-hidden rounded-xl border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>
              <Skeleton className="h-4 w-14" />
            </TableHead>
            <TableHead className="w-28">
              <Skeleton className="ml-auto h-4 w-12" />
            </TableHead>
            <TableHead className="w-36">
              <Skeleton className="h-4 w-16" />
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Array.from({ length: rows }, (_, row) => (
            <TableRow key={row}>
              <TableCell>
                <div className="flex items-center gap-3">
                  <Skeleton className="size-9 shrink-0 rounded-full" />
                  <Skeleton className="h-4 w-36" />
                </div>
              </TableCell>
              <TableCell>
                <Skeleton className="ml-auto h-4 w-8" />
              </TableCell>
              <TableCell>
                <Skeleton className="h-4 w-20" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export function PlaylistCardsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {Array.from({ length: count }, (_, i) => (
        <li key={i}>
          <div className="bg-muted/40 flex min-h-[8.5rem] flex-col justify-between gap-6 rounded-2xl border p-4">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-3 w-28" />
          </div>
        </li>
      ))}
    </ul>
  )
}

export function PlaylistDetailSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="bg-muted/40 flex flex-col gap-4 rounded-2xl border p-5 sm:p-6">
        <Skeleton className="h-7 w-48" />
        <Skeleton className="h-4 w-72 max-w-full" />
        <Skeleton className="h-3 w-24" />
        <div className="flex flex-wrap gap-2 pt-2">
          <Skeleton className="h-8 w-20 rounded-md" />
          <Skeleton className="h-8 w-16 rounded-md" />
          <Skeleton className="h-8 w-20 rounded-md" />
        </div>
      </div>
      <div className="flex flex-col gap-3">
        {Array.from({ length: 5 }, (_, i) => (
          <div
            key={i}
            className="flex items-center gap-3 rounded-xl border px-3 py-2.5"
          >
            <Skeleton className="size-10 shrink-0 rounded-md" />
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-3 w-28" />
            </div>
            <Skeleton className="h-3 w-10" />
          </div>
        ))}
      </div>
    </div>
  )
}

export function JobCardsSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="rounded-xl border p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 flex-1 flex-col gap-2">
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-3 w-32" />
            </div>
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>
          <Skeleton className="mt-4 h-2 w-full rounded-full" />
          <div className="mt-3 flex gap-4">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-3 w-12" />
          </div>
        </div>
      ))}
    </div>
  )
}

export function ChatThreadSkeleton() {
  return (
    <div className="flex flex-col gap-6 py-2">
      <div className="flex flex-col gap-2 self-end max-w-[85%]">
        <Skeleton className="h-16 w-64 rounded-2xl" />
      </div>
      <div className="flex flex-col gap-2 max-w-[85%]">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-4 w-72 max-w-full" />
        <Skeleton className="h-4 w-56" />
        <Skeleton className="mt-2 h-20 w-full max-w-sm rounded-xl" />
      </div>
      <div className="flex flex-col gap-2 self-end max-w-[85%]">
        <Skeleton className="h-12 w-48 rounded-2xl" />
      </div>
    </div>
  )
}

export function ArtistHeaderSkeleton() {
  return (
    <div className="flex items-center gap-3">
      <Skeleton className="size-14 shrink-0 rounded-full" />
      <div className="flex min-w-0 flex-col gap-2">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-4 w-48" />
      </div>
    </div>
  )
}
