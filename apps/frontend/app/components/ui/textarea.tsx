import * as React from "react"

import { cn } from "~/lib/utils"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-16 w-full appearance-none rounded-md bg-[var(--bg-field)] px-2 py-1.5 text-base text-[var(--fg-base)] shadow-borders-base outline-none transition-[color,background-color,box-shadow]",
        "placeholder:text-[var(--fg-muted)]",
        "hover:bg-[var(--bg-field-hover)]",
        "focus-visible:shadow-borders-interactive-with-active",
        "disabled:cursor-not-allowed disabled:bg-[var(--bg-disabled)] disabled:text-[var(--fg-disabled)] disabled:placeholder:text-[var(--fg-disabled)]",
        "aria-invalid:shadow-borders-error",
        "md:text-sm",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
