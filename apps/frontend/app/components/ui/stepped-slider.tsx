import { useCallback, useRef } from "react"

import { cn } from "~/lib/utils"

type SteppedSliderProps = {
  value: number
  onValueChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  disabled?: boolean
  className?: string
  "aria-label"?: string
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function snap(value: number, min: number, max: number, step: number): number {
  const snapped = Math.round(value / step) * step
  return clamp(snapped, min, max)
}

function SteppedSlider({
  value,
  onValueChange,
  min = 0,
  max = 100,
  step = 5,
  disabled = false,
  className,
  "aria-label": ariaLabel,
}: SteppedSliderProps) {
  const trackRef = useRef<HTMLDivElement>(null)
  const draggingRef = useRef(false)

  const setFromClientX = useCallback(
    (clientX: number) => {
      const track = trackRef.current
      if (!track) return
      const rect = track.getBoundingClientRect()
      if (rect.width <= 0) return
      const ratio = (clientX - rect.left) / rect.width
      const raw = min + ratio * (max - min)
      onValueChange(snap(raw, min, max, step))
    },
    [max, min, onValueChange, step],
  )

  const progress = ((value - min) / (max - min)) * 100

  return (
    <div
      ref={trackRef}
      role="slider"
      tabIndex={disabled ? -1 : 0}
      aria-label={ariaLabel}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={value}
      aria-disabled={disabled || undefined}
      className={cn(
        "relative h-4 cursor-pointer touch-none select-none",
        disabled && "pointer-events-none opacity-50",
        className,
      )}
      onPointerDown={(event) => {
        if (disabled) return
        draggingRef.current = true
        event.currentTarget.setPointerCapture(event.pointerId)
        setFromClientX(event.clientX)
      }}
      onPointerMove={(event) => {
        if (!draggingRef.current) return
        setFromClientX(event.clientX)
      }}
      onPointerUp={() => {
        draggingRef.current = false
      }}
      onPointerCancel={() => {
        draggingRef.current = false
      }}
      onKeyDown={(event) => {
        if (disabled) return
        if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
          event.preventDefault()
          onValueChange(clamp(value - step, min, max))
        } else if (event.key === "ArrowRight" || event.key === "ArrowUp") {
          event.preventDefault()
          onValueChange(clamp(value + step, min, max))
        } else if (event.key === "Home") {
          event.preventDefault()
          onValueChange(min)
        } else if (event.key === "End") {
          event.preventDefault()
          onValueChange(max)
        }
      }}
    >
      <div className="pointer-events-none absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-muted-foreground/35" />
      <div
        className="pointer-events-none absolute top-1/2 left-0 h-1 -translate-y-1/2 rounded-full bg-foreground transition-[width] duration-150 ease-out"
        style={{ width: `${progress}%` }}
      />
      <div
        className="pointer-events-none absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-foreground shadow-sm transition-[left] duration-150 ease-out"
        style={{ left: `${progress}%` }}
      />
    </div>
  )
}

export { SteppedSlider }
