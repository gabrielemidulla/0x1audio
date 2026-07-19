import type { ReactNode } from "react"

import { Skeleton } from "~/components/ui/skeleton"
import { greetingName } from "~/lib/greeting"
import { cn } from "~/lib/utils"

type GreetingStageProps = {
  /** Preferred greeting label (display name). */
  name?: string | null
  /** Fallback when name is empty. */
  email?: string | null
  /** When true, show a name skeleton (user still loading). */
  loading?: boolean
  children: ReactNode
  className?: string
}

/** Greeting + prompter with a soft coral/pink/blue glow centered on the input. */
export function GreetingStage({
  name,
  email,
  loading = false,
  children,
  className,
}: GreetingStageProps) {
  const label = name?.trim() || (email ? greetingName(email) : null)

  return (
    <div
      className={cn(
        "relative isolate flex w-full max-w-xl flex-col items-center gap-6",
        className,
      )}
    >
      <div
        className="greeting-glow pointer-events-none absolute inset-x-[-30%] top-[42%] bottom-[-40%] -z-10"
        aria-hidden
      >
        <span className="greeting-glow-blob greeting-glow-blob--warm" />
        <span className="greeting-glow-blob greeting-glow-blob--rose" />
        <span className="greeting-glow-blob greeting-glow-blob--cool" />
      </div>
      <h1 className="relative flex flex-wrap items-baseline justify-center gap-x-2 text-3xl font-medium tracking-tight sm:text-4xl">
        <span>Your turn,</span>
        {loading || !label ? (
          <Skeleton className="inline-block h-9 w-40 align-baseline sm:h-10" />
        ) : (
          <span>{label}.</span>
        )}
      </h1>
      <div className="relative w-full">{children}</div>
    </div>
  )
}
