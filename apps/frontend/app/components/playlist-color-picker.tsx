import { PLAYLIST_COLORS } from "~/client/constants.gen"
import type { PlaylistColor } from "~/lib/api"
import { cn } from "~/lib/utils"

export function PlaylistColorPicker({
  value,
  onChange,
  optional = false,
}: {
  value: PlaylistColor | null
  onChange: (next: PlaylistColor) => void
  optional?: boolean
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium">
          Color{optional ? " (optional)" : ""}
        </span>
        {value ? (
          <span className="text-muted-foreground text-xs">
            {PLAYLIST_COLORS.find((c) => c.value === value)?.label}
          </span>
        ) : null}
      </div>
      <div className="grid grid-cols-6 gap-1.5 sm:grid-cols-8">
        {PLAYLIST_COLORS.map((color) => {
          const selected = value === color.value
          return (
            <button
              key={color.value}
              type="button"
              title={`${color.label} — ${color.hint}`}
              aria-label={color.label}
              aria-pressed={selected}
              onClick={() => onChange(color.value)}
              className={cn(
                "size-8 rounded-full border-2 transition-[transform,box-shadow] duration-150",
                "hover:scale-105 focus-visible:ring-ring focus-visible:ring-2 focus-visible:outline-none",
                selected
                  ? "border-foreground scale-105 shadow-sm"
                  : "border-transparent",
              )}
              style={{
                backgroundImage: `linear-gradient(135deg, ${color.hexes[0]} 0%, ${color.hexes[1]} 55%, ${color.hexes[2]} 100%)`,
              }}
            />
          )
        })}
      </div>
    </div>
  )
}
