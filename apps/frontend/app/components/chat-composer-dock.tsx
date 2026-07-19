import { useEffect, useRef, type ReactNode } from "react"

import { useAudioPlayer } from "~/lib/audio-player"
import { cn } from "~/lib/utils"

type ChatComposerDockProps = {
  children: ReactNode
  composer: ReactNode
  className?: string
  /** Change this when the thread should pin to the latest message. */
  scrollKey?: string | number
  /** Extra viewport room under the thread so the next assistant reply can fill in. */
  leaveReplyRoom?: boolean
}

export function ChatComposerDock({
  children,
  composer,
  className,
  scrollKey,
  leaveReplyRoom = false,
}: ChatComposerDockProps) {
  const player = useAudioPlayer()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [scrollKey, leaveReplyRoom])

  return (
    <div className={cn("relative flex min-h-0 flex-1 flex-col", className)}>
      <div
        className={cn(
          "no-scrollbar min-h-0 flex-1 overflow-x-hidden overflow-y-auto",
          player.track ? "pb-44" : "pb-28",
        )}
      >
        {children}
        <div
          className={cn(
            "w-full shrink-0 transition-[min-height] duration-300 ease-out",
            leaveReplyRoom ? "min-h-[min(58svh,32rem)]" : "min-h-8",
          )}
          aria-hidden
        />
        <div ref={bottomRef} className="h-px w-full shrink-0" aria-hidden />
      </div>

      <div
        className={cn(
          "pointer-events-none absolute inset-x-0 bottom-0 z-10 flex flex-col",
          player.track && "bottom-20",
        )}
      >
        <div
          className="h-20 shrink-0 bg-gradient-to-t from-background from-0% to-transparent to-100%"
          aria-hidden
        />
        <div className="pointer-events-auto bg-background pb-4">
          {composer}
        </div>
      </div>
    </div>
  )
}
