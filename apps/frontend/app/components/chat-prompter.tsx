import { useState, type FormEvent } from "react"
import { PaperPlaneRight, Stop } from "@phosphor-icons/react"

import { Button } from "~/components/ui/button"
import { cn } from "~/lib/utils"

type ChatPrompterProps = {
  placeholder?: string
  disabled?: boolean
  generating?: boolean
  autoFocus?: boolean
  className?: string
  value?: string
  onValueChange?: (value: string) => void
  onSubmit: (message: string) => void | Promise<void>
  onStop?: () => void
}

export function ChatPrompter({
  placeholder = "Ask your library…",
  disabled = false,
  generating = false,
  autoFocus = false,
  className,
  value: controlledValue,
  onValueChange,
  onSubmit,
  onStop,
}: ChatPrompterProps) {
  const [uncontrolledValue, setUncontrolledValue] = useState("")
  const [sending, setSending] = useState(false)
  const isControlled = controlledValue !== undefined
  const value = isControlled ? controlledValue : uncontrolledValue

  function setValue(next: string) {
    if (isControlled) onValueChange?.(next)
    else setUncontrolledValue(next)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const message = value.trim()
    if (!message || sending || disabled || generating) return
    setSending(true)
    setValue("")
    try {
      await onSubmit(message)
    } finally {
      setSending(false)
    }
  }

  return (
    <form
      onSubmit={(event) => {
        void handleSubmit(event)
      }}
      className={cn(
        "flex w-full items-center gap-2 rounded-full border bg-background px-4 py-2 shadow-sm",
        className,
      )}
    >
      <input
        type="text"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={placeholder}
        disabled={disabled || sending || generating}
        autoFocus={autoFocus}
        className="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground disabled:opacity-50"
      />
      {generating ? (
        <Button
          type="button"
          size="icon-sm"
          variant="ghost"
          aria-label="Stop generating"
          onClick={() => onStop?.()}
        >
          <Stop weight="fill" />
        </Button>
      ) : (
        <Button
          type="submit"
          size="icon-sm"
          variant="ghost"
          disabled={disabled || sending || !value.trim()}
          aria-label="Send"
        >
          <PaperPlaneRight weight="fill" />
        </Button>
      )}
    </form>
  )
}
