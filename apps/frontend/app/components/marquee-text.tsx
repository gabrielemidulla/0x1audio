import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react"

import { cn } from "~/lib/utils"

type MarqueeTextProps = {
  children: ReactNode
  className?: string
  style?: CSSProperties
  /** Remeasure when this changes (track id + title/artist string). */
  contentKey?: string
}

/**
 * Spotify/Apple-style title scroll: only animates when the text overflows
 * its container. Holds at each end, then eases back.
 */
export function MarqueeText({
  children,
  className,
  style,
  contentKey,
}: MarqueeTextProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const [distance, setDistance] = useState(0)

  useEffect(() => {
    const container = containerRef.current
    const content = contentRef.current
    if (!container || !content) return

    const measure = () => {
      setDistance(Math.max(0, content.scrollWidth - container.clientWidth))
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(container)
    observer.observe(content)
    return () => observer.disconnect()
  }, [contentKey])

  // ~28px/s of travel, clamped so short overflows aren't frantic.
  const durationSec = Math.min(18, Math.max(5, distance / 28))

  return (
    <div
      ref={containerRef}
      className={cn(
        "min-w-0 overflow-hidden",
        distance > 0 && "player-marquee-mask",
        className,
      )}
      style={style}
    >
      <div
        ref={contentRef}
        className={cn(
          "inline-block max-w-none whitespace-nowrap",
          distance > 0 && "player-marquee",
        )}
        style={
          distance > 0
            ? ({
                "--marquee-distance": `${distance}px`,
                "--marquee-duration": `${durationSec}s`,
              } as CSSProperties)
            : undefined
        }
      >
        {children}
      </div>
    </div>
  )
}
