import { useLayoutEffect, useRef, useState } from "react"

import { cn } from "~/lib/utils"

type SegmentedControlOption<T extends string> = {
  value: T
  label: string
}

type SegmentedControlProps<T extends string> = {
  value: T | null
  options: readonly SegmentedControlOption<T>[]
  onValueChange: (value: T) => void
  disabled?: boolean
  className?: string
  "aria-label"?: string
}

function SegmentedControl<T extends string>({
  value,
  options,
  onValueChange,
  disabled = false,
  className,
  "aria-label": ariaLabel,
}: SegmentedControlProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null)
  const buttonRefs = useRef<Array<HTMLButtonElement | null>>([])
  const [indicator, setIndicator] = useState<{
    left: number
    width: number
    visible: boolean
  }>({ left: 0, width: 0, visible: false })

  useLayoutEffect(() => {
    const container = containerRef.current
    if (!container) return

    const update = () => {
      const index = value == null ? -1 : options.findIndex((option) => option.value === value)
      const button = index >= 0 ? buttonRefs.current[index] : null
      if (!button) {
        setIndicator((prev) => ({ ...prev, visible: false }))
        return
      }
      setIndicator({
        left: button.offsetLeft,
        width: button.offsetWidth,
        visible: true,
      })
    }

    update()
    const observer = new ResizeObserver(update)
    observer.observe(container)
    for (const button of buttonRefs.current) {
      if (button) observer.observe(button)
    }
    return () => observer.disconnect()
  }, [value, options])

  return (
    <div
      ref={containerRef}
      role="radiogroup"
      aria-label={ariaLabel}
      className={cn(
        "relative flex gap-0.5 rounded-lg bg-muted p-1",
        disabled && "pointer-events-none opacity-50",
        className,
      )}
    >
      <div
        aria-hidden
        className={cn(
          "pointer-events-none absolute top-1 bottom-1 left-0 rounded-md bg-foreground shadow-sm",
          "transition-[transform,width,opacity] duration-200 ease-out",
          indicator.visible ? "opacity-100" : "opacity-0",
        )}
        style={{
          width: indicator.width,
          transform: `translateX(${indicator.left}px)`,
        }}
      />
      {options.map((option, index) => {
        const selected = value === option.value
        return (
          <button
            key={option.value}
            ref={(node) => {
              buttonRefs.current[index] = node
            }}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onValueChange(option.value)}
            className={cn(
              "relative z-[1] flex-1 rounded-md px-2.5 py-1.5 text-center text-xs font-medium transition-colors duration-200",
              "outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
              selected
                ? "text-background"
                : "bg-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

export { SegmentedControl }
export type { SegmentedControlOption, SegmentedControlProps }
