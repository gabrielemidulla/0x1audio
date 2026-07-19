import type { ReactNode } from "react"
import { CaretLeft, CaretRight } from "@phosphor-icons/react"

import { Button } from "~/components/ui/button"
import { cn } from "~/lib/utils"

export type OnboardingSlide = {
  title: string
  description: string
  content: ReactNode
}

type OnboardingShellProps = {
  slides: OnboardingSlide[]
  step: number
  canBack?: boolean
  canForward?: boolean
  onBack?: () => void
  onForward?: () => void
  className?: string
}

export function OnboardingShell({
  slides,
  step,
  canBack = false,
  canForward = false,
  onBack,
  onForward,
  className,
}: OnboardingShellProps) {
  const totalSteps = Math.max(slides.length, 1)
  const index = Math.min(Math.max(step, 1), totalSteps) - 1

  return (
    <div className="relative flex min-h-svh items-center justify-center overflow-hidden p-6">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_20%_0%,oklch(0.92_0.04_220)_0%,transparent_55%),radial-gradient(ellipse_at_90%_10%,oklch(0.93_0.03_80)_0%,transparent_45%),linear-gradient(180deg,oklch(0.985_0.005_240),oklch(0.96_0.01_230))] dark:bg-[radial-gradient(ellipse_at_15%_0%,oklch(0.28_0.04_230)_0%,transparent_50%),radial-gradient(ellipse_at_90%_20%,oklch(0.26_0.03_80)_0%,transparent_40%),linear-gradient(180deg,oklch(0.16_0.01_240),oklch(0.14_0.01_230))]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.35] [background-image:linear-gradient(to_right,oklch(0.7_0_0/0.06)_1px,transparent_1px),linear-gradient(to_bottom,oklch(0.7_0_0/0.06)_1px,transparent_1px)] [background-size:48px_48px] dark:opacity-20"
      />

      <div className={cn("relative z-10 w-full max-w-md", className)}>
        <div className="mb-8 flex w-full flex-col items-center gap-5 text-center">
          <div className="flex w-full justify-center">
            <img
              src="/logo.svg"
              alt="0x1audio"
              className="mx-auto h-8 w-auto dark:invert"
            />
          </div>

          <div className="flex w-full max-w-[14rem] items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8 shrink-0 rounded-full"
              disabled={!canBack}
              aria-label="Previous step"
              onClick={onBack}
            >
              <CaretLeft className="size-4" weight="bold" />
            </Button>

            <div
              className="flex min-w-0 flex-1 items-center gap-1.5"
              aria-label={`Step ${index + 1} of ${totalSteps}`}
            >
              {Array.from({ length: totalSteps }, (_, pillIndex) => {
                const active = pillIndex <= index
                return (
                  <span
                    key={pillIndex}
                    className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-foreground/15"
                  >
                    <span
                      className={cn(
                        "absolute inset-y-0 left-0 rounded-full bg-foreground/80 transition-[width] duration-500 ease-out motion-reduce:transition-none",
                        active ? "w-full" : "w-0",
                      )}
                    />
                  </span>
                )
              })}
            </div>

            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8 shrink-0 rounded-full"
              disabled={!canForward}
              aria-label="Next step"
              onClick={onForward}
            >
              <CaretRight className="size-4" weight="bold" />
            </Button>
          </div>
        </div>

        {/* overflow-clip (not hidden): avoid a scroll container so focus can't scroll to off-screen slides */}
        <div className="w-full overflow-x-clip">
          <div
            className="flex w-full transition-transform duration-500 ease-out motion-reduce:transition-none"
            style={{ transform: `translateX(-${index * 100}%)` }}
          >
            {slides.map((slide, panelIndex) => (
              <div
                key={panelIndex}
                className="flex w-full shrink-0 grow-0 basis-full flex-col gap-6 px-0.5"
                aria-hidden={panelIndex !== index}
                // Prevent focus (and scroll-into-view) on off-screen slides
                {...(panelIndex !== index ? { inert: true } : {})}
              >
                <div className="w-full space-y-2 text-center">
                  <h1 className="text-2xl font-medium tracking-tight">
                    {slide.title}
                  </h1>
                  <p className="text-muted-foreground text-sm leading-relaxed">
                    {slide.description}
                  </p>
                </div>
                {slide.content}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
