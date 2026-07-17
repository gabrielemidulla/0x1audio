import { useMemo, useRef } from "react"

import { cn } from "~/lib/utils"

type TrackWaveformProps = {
  samples: number[]
  progress: number
  duration: number
  currentTime: number
  onSeek: (seconds: number) => void
  className?: string
}

const MAX_BARS = 96

function downsample(samples: number[], count: number): number[] {
  if (samples.length <= count) return samples
  const bars: number[] = []
  const bucket = samples.length / count
  for (let i = 0; i < count; i += 1) {
    const start = Math.floor(i * bucket)
    const end = Math.floor((i + 1) * bucket)
    let peak = 0
    for (let j = start; j < end; j += 1) {
      peak = Math.max(peak, samples[j] ?? 0)
    }
    bars.push(peak)
  }
  return bars
}

export function TrackWaveform({
  samples,
  progress,
  duration,
  currentTime,
  onSeek,
  className,
}: TrackWaveformProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const bars = useMemo(() => downsample(samples, MAX_BARS), [samples])
  const dragging = useRef(false)

  function seekFromClientX(clientX: number) {
    const el = containerRef.current
    if (!el || duration <= 0) return
    const rect = el.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
    onSeek(ratio * duration)
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative flex h-10 min-w-0 flex-1 items-center overflow-hidden rounded-md",
        className,
      )}
    >
      <div className="pointer-events-none flex h-full w-full items-center gap-px" aria-hidden>
        {bars.map((bar, index) => {
          const active = index / Math.max(bars.length - 1, 1) <= progress
          return (
            <span
              key={index}
              className={cn(
                "min-w-px flex-1 rounded-full",
                active
                  ? "bg-[var(--player-wave-active,var(--color-primary))]"
                  : "bg-[var(--player-wave-idle,color-mix(in_oklab,var(--color-muted-foreground)_30%,transparent))]",
              )}
              style={{ height: `${Math.max(8, Math.round(bar * 36))}px` }}
            />
          )
        })}
      </div>
      <input
        type="range"
        min={0}
        max={duration || 0}
        step={0.1}
        value={Math.min(currentTime, duration || 0)}
        aria-label="Seek"
        className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
        onChange={(event) => onSeek(Number(event.target.value))}
        onPointerDown={() => {
          dragging.current = true
        }}
        onPointerMove={(event) => {
          if (!dragging.current) return
          seekFromClientX(event.clientX)
        }}
        onPointerUp={(event) => {
          dragging.current = false
          seekFromClientX(event.clientX)
        }}
        onPointerCancel={() => {
          dragging.current = false
        }}
      />
    </div>
  )
}
