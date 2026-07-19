import type { ReactNode } from "react"

import { cn } from "~/lib/utils"

type RevealProps = {
  visible: boolean
  delayClass?: string
  className?: string
  children: ReactNode
}

/** Soft blur/fade entrance used on dashboard-style pages. */
export function Reveal({
  visible,
  delayClass,
  className,
  children,
}: RevealProps) {
  return (
    <div
      className={cn(
        "transition-[opacity,filter,transform] duration-500 ease-out",
        "motion-reduce:translate-y-0 motion-reduce:opacity-100 motion-reduce:blur-none motion-reduce:transition-none",
        delayClass,
        visible
          ? "translate-y-0 opacity-100 blur-none"
          : "translate-y-2 opacity-0 blur-md",
        className,
      )}
    >
      {children}
    </div>
  )
}
