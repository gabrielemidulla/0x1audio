import type { ReactNode } from "react"

import { greetingName } from "~/lib/greeting"
import { cn } from "~/lib/utils"

type GreetingStageProps = {
  email: string
  children: ReactNode
  className?: string
}

/** Greeting + prompter with a soft coral/pink/blue glow centered on the input. */
export function GreetingStage({ email, children, className }: GreetingStageProps) {
  return (
    <div
      className={cn(
        "relative isolate flex w-full max-w-xl flex-col items-center gap-6",
        className,
      )}
    >
      <div className="greeting-glow pointer-events-none absolute inset-x-[-30%] top-[42%] bottom-[-40%] -z-10" aria-hidden>
        <span className="greeting-glow-blob greeting-glow-blob--warm" />
        <span className="greeting-glow-blob greeting-glow-blob--rose" />
        <span className="greeting-glow-blob greeting-glow-blob--cool" />
      </div>
      <h1 className="relative text-3xl font-medium tracking-tight sm:text-4xl">
        Your turn, {greetingName(email)}.
      </h1>
      <div className="relative w-full">{children}</div>
    </div>
  )
}
