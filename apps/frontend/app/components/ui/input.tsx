import * as React from "react"
import { Input as InputPrimitive } from "@base-ui/react/input"

import { cn } from "~/lib/utils"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      className={cn(
        "h-8 w-full min-w-0 appearance-none rounded-md bg-[var(--bg-field)] px-2 py-1.5 text-base text-[var(--fg-base)] shadow-borders-base outline-none transition-[color,background-color,box-shadow]",
        "placeholder:text-[var(--fg-muted)]",
        "hover:bg-[var(--bg-field-hover)]",
        "focus-visible:shadow-borders-interactive-with-active",
        "disabled:cursor-not-allowed disabled:bg-[var(--bg-disabled)] disabled:text-[var(--fg-disabled)] disabled:placeholder:text-[var(--fg-disabled)]",
        "aria-invalid:shadow-borders-error",
        "file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-[var(--fg-base)]",
        "md:text-sm",
        className
      )}
      {...props}
    />
  )
}

export { Input }
