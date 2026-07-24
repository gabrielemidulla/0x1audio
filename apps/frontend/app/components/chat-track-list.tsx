import { useState } from "react"
import { Stack } from "@phosphor-icons/react"

import { ChatTrackRow } from "~/components/chat-track-row"
import { SlidingHoverList } from "~/components/sliding-hover-list"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "~/components/ui/dialog"
import { trackCoverUrl, type TrackOut } from "~/lib/api"
import { cn } from "~/lib/utils"

import { FALLBACK_COVER_COLOR } from "~/client/constants.gen"

const STACK_THRESHOLD = 3

export function ChatTrackList({ tracks }: { tracks: TrackOut[] }) {
  if (tracks.length === 0) return null

  if (tracks.length <= STACK_THRESHOLD) {
    return <ChatTrackRows tracks={tracks} />
  }

  return <ChatTrackStack tracks={tracks} />
}

function ChatTrackRows({
  tracks,
  className,
}: {
  tracks: TrackOut[]
  className?: string
}) {
  return (
    <SlidingHoverList
      as="ul"
      className={cn(
        "flex w-full max-w-[min(40rem,100%)] flex-col gap-0.5",
        className,
      )}
      indicatorClassName="rounded-lg bg-muted"
    >
      {tracks.map((track) => (
        <li key={track.id} data-sliding-item className="relative z-[1]">
          <ChatTrackRow track={track} />
        </li>
      ))}
    </SlidingHoverList>
  )
}

function ChatTrackStack({ tracks }: { tracks: TrackOut[] }) {
  const [open, setOpen] = useState(false)
  const preview = tracks.slice(0, 3)

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="hover:bg-muted group flex w-fit max-w-[min(40rem,100%)] items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors"
      >
        <VinylStack tracks={preview} />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">
            {tracks.length} tracks
          </span>
          <span className="text-muted-foreground block truncate text-xs">
            {tracks
              .slice(0, 3)
              .map((track) => track.title)
              .join(" · ")}
          </span>
        </span>
        <Stack className="text-muted-foreground size-4 shrink-0 opacity-70 group-hover:opacity-100" />
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Tracks</DialogTitle>
            <DialogDescription>
              {tracks.length} tracks from this reply
            </DialogDescription>
          </DialogHeader>
          <ChatTrackRows
            tracks={tracks}
            className="max-h-[min(24rem,60vh)] max-w-none overflow-y-auto -mx-1 px-1"
          />
        </DialogContent>
      </Dialog>
    </>
  )
}

function VinylStack({ tracks }: { tracks: TrackOut[] }) {
  return (
    <span className="relative h-11 w-14 shrink-0" aria-hidden>
      {tracks.map((track, index) => {
        const fromBack = tracks.length - 1 - index
        const offset = fromBack * 6
        const rotate = (fromBack - 1) * 6
        return (
          <span
            key={track.id}
            className={cn(
              "absolute top-0 left-0 size-10 overflow-hidden rounded-full shadow-sm ring-2 ring-background",
            )}
            style={{
              backgroundColor: track.cover_color || FALLBACK_COVER_COLOR,
              transform: `translate(${offset}px, ${fromBack * 1}px) rotate(${rotate}deg)`,
              zIndex: index + 1,
            }}
          >
            {track.has_cover ? (
              <img
                src={trackCoverUrl(track.id)}
                alt=""
                className="absolute inset-0 size-full object-cover"
              />
            ) : null}
            <span className="absolute inset-0 rounded-full ring-1 ring-inset ring-black/10" />
            <span className="absolute top-1/2 left-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-background/90 shadow-sm" />
          </span>
        )
      })}
    </span>
  )
}
