import { useEffect, useRef, type ReactNode } from "react"

import { useAudioPlayer } from "~/lib/audio-player"
import { cn } from "~/lib/utils"

type ChatComposerDockProps = {
  children: ReactNode
  composer: ReactNode
  className?: string
  /** Change this when the thread should pin to the latest message. */
  scrollKey?: string | number
}

export function ChatComposerDock({
  children,
  composer,
  className,
  scrollKey,
}: ChatComposerDockProps) {
  const player = useAudioPlayer()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [scrollKey])

  return (
    <div className={cn("relative flex min-h-0 flex-1 flex-col", className)}>
      <div
        className={cn(
          "no-scrollbar min-h-0 flex-1 overflow-x-hidden overflow-y-auto",
          player.track ? "pb-44" : "pb-28",
        )}
      >
        {children}
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
