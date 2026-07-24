import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ElementType,
  type HTMLAttributes,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react"

import { cn } from "~/lib/utils"

type Indicator = {
  top: number
  height: number
  scale: number
  opacity: number
}

/** Enter animates up from this; leave animates down to it before fading out. */
const PARK_SCALE = 0.4

type SlidingHoverListProps = {
  children: ReactNode
  className?: string
  indicatorClassName?: string
  as?: ElementType
  /** Track `data-selected` (cmdk) so keyboard selection moves the pill too. */
  followSelected?: boolean
} & Omit<HTMLAttributes<HTMLElement>, "children" | "className">

/** Shared sliding hover pill for lists. Mark rows with `data-sliding-item`. */
export function SlidingHoverList({
  children,
  className,
  indicatorClassName,
  as: Comp = "div",
  followSelected = false,
  onPointerOver,
  onPointerLeave,
  onScroll,
  ...props
}: SlidingHoverListProps) {
  const containerRef = useRef<HTMLElement | null>(null)
  const activeItemRef = useRef<HTMLElement | null>(null)
  const enterFrameRef = useRef<number | null>(null)
  const [indicator, setIndicator] = useState<Indicator>({
    top: 0,
    height: 0,
    scale: PARK_SCALE,
    opacity: 0,
  })
  const [instant, setInstant] = useState(false)

  const cancelEnter = useCallback(() => {
    if (enterFrameRef.current != null) {
      cancelAnimationFrame(enterFrameRef.current)
      enterFrameRef.current = null
    }
  }, [])

  const moveTo = useCallback(
    (item: HTMLElement, mode: "enter" | "slide") => {
      cancelEnter()
      activeItemRef.current = item
      const top = item.offsetTop
      const height = item.offsetHeight

      if (mode === "slide") {
        setInstant(false)
        setIndicator({ top, height, scale: 1, opacity: 1 })
        return
      }

      setInstant(true)
      setIndicator({ top, height, scale: PARK_SCALE, opacity: 1 })
      enterFrameRef.current = requestAnimationFrame(() => {
        enterFrameRef.current = requestAnimationFrame(() => {
          enterFrameRef.current = null
          setInstant(false)
          setIndicator({ top, height, scale: 1, opacity: 1 })
        })
      })
    },
    [cancelEnter],
  )

  const clear = useCallback(() => {
    cancelEnter()
    activeItemRef.current = null
    setInstant(false)
    setIndicator((prev) => ({ ...prev, scale: PARK_SCALE, opacity: 0 }))
  }, [cancelEnter])

  const syncSelected = useCallback(() => {
    const container = containerRef.current
    if (!container) return
    const selected = container.querySelector<HTMLElement>(
      '[data-sliding-item][data-selected="true"]',
    )
    if (!selected) {
      clear()
      return
    }
    if (activeItemRef.current === selected) return
    const mode = activeItemRef.current == null ? "enter" : "slide"
    moveTo(selected, mode)
  }, [clear, moveTo])

  useEffect(() => {
    if (!followSelected) return
    const container = containerRef.current
    if (!container) return

    syncSelected()
    const observer = new MutationObserver(() => syncSelected())
    observer.observe(container, {
      attributes: true,
      subtree: true,
      attributeFilter: ["data-selected"],
      childList: true,
    })
    return () => observer.disconnect()
  }, [followSelected, syncSelected, children])

  const handlePointerOver = useCallback(
    (event: ReactPointerEvent<HTMLElement>) => {
      onPointerOver?.(event)
      if (event.defaultPrevented) return
      if (followSelected) return
      const target = event.target
      if (!(target instanceof Element)) return
      const item = target.closest("[data-sliding-item]")
      if (!(item instanceof HTMLElement)) return
      if (!containerRef.current?.contains(item)) return
      if (activeItemRef.current === item) return
      const mode = activeItemRef.current == null ? "enter" : "slide"
      moveTo(item, mode)
    },
    [followSelected, moveTo, onPointerOver],
  )

  return (
    <Comp
      ref={containerRef}
      className={cn("relative", className)}
      onPointerOver={handlePointerOver}
      onPointerLeave={(event: ReactPointerEvent<HTMLElement>) => {
        onPointerLeave?.(event)
        if (event.defaultPrevented) return
        if (followSelected) {
          syncSelected()
          return
        }
        clear()
      }}
      onScroll={(event: React.UIEvent<HTMLElement>) => {
        onScroll?.(event)
        if (activeItemRef.current) moveTo(activeItemRef.current, "slide")
      }}
      {...props}
    >
      <div
        aria-hidden
        className={cn(
          "pointer-events-none absolute top-0 right-0 left-0 z-0 origin-center rounded-md",
          !instant &&
            "transition-[transform,height,opacity] duration-200 ease-out",
          "motion-reduce:transition-none",
          indicatorClassName ?? "bg-muted",
        )}
        style={{
          height: indicator.height || undefined,
          opacity: indicator.opacity,
          transform: `translateY(${indicator.top}px) scale(${indicator.scale})`,
        }}
      />
      {children}
    </Comp>
  )
}
