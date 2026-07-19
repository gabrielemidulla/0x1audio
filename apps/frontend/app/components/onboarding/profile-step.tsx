import { useEffect, useRef, useState } from "react"
import { User as UserIcon } from "@phosphor-icons/react"

import { Avatar, AvatarFallback, AvatarImage } from "~/components/ui/avatar"
import { Button } from "~/components/ui/button"
import { Input } from "~/components/ui/input"
import { Label } from "~/components/ui/label"
import { ALLOWED_IMAGE_MIME_TYPES } from "~/client/constants.gen"
import { cn } from "~/lib/utils"

const ACCEPT_IMAGE = ALLOWED_IMAGE_MIME_TYPES.join(",")

export type ProfileStepValues = {
  displayName: string
  avatarFile: File | null
}

type ProfileStepProps = {
  initialDisplayName?: string
  initialPreviewUrl?: string | null
  pending?: boolean
  error?: string | null
  submitLabel?: string
  autoFocus?: boolean
  onSubmit: (values: ProfileStepValues) => void | Promise<void>
}

export function ProfileStep({
  initialDisplayName = "",
  initialPreviewUrl = null,
  pending = false,
  error = null,
  submitLabel = "Continue",
  autoFocus = false,
  onSubmit,
}: ProfileStepProps) {
  const [displayName, setDisplayName] = useState(initialDisplayName)
  const [avatarFile, setAvatarFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(initialPreviewUrl)
  const displayNameRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!avatarFile) return
    const url = URL.createObjectURL(avatarFile)
    setPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [avatarFile])

  useEffect(() => {
    if (!autoFocus) return
    displayNameRef.current?.focus({ preventScroll: true })
  }, [autoFocus])

  return (
    <form
      className="flex flex-col gap-5 rounded-2xl border bg-card/80 p-6 shadow-lg backdrop-blur-sm"
      onSubmit={(event) => {
        event.preventDefault()
        void onSubmit({
          displayName: displayName.trim(),
          avatarFile,
        })
      }}
    >
      <div className="flex flex-col items-center gap-3">
        <label
          className={cn(
            "group relative cursor-pointer",
            pending && "pointer-events-none opacity-60",
          )}
        >
          <Avatar className="size-20 data-[size=default]:size-20">
            {previewUrl ? <AvatarImage src={previewUrl} alt="" /> : null}
            <AvatarFallback className="text-base">
              <UserIcon className="size-7" />
            </AvatarFallback>
          </Avatar>
          <span className="text-muted-foreground mt-2 block text-center text-xs">
            {previewUrl ? "Change photo" : "Add photo"}
          </span>
          <input
            type="file"
            accept={ACCEPT_IMAGE}
            className="sr-only"
            disabled={pending}
            onChange={(event) => {
              const file = event.target.files?.[0] ?? null
              setAvatarFile(file)
              if (!file) setPreviewUrl(initialPreviewUrl)
            }}
          />
        </label>
      </div>

      <div className="flex flex-col gap-2">
        <Label htmlFor="display-name">Display name</Label>
        <Input
          ref={displayNameRef}
          id="display-name"
          name="display_name"
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
          placeholder="How should we call you?"
          maxLength={120}
          required
          disabled={pending}
        />
      </div>

      {error ? <p className="text-destructive text-sm">{error}</p> : null}

      <Button type="submit" className="w-full" disabled={pending || !displayName.trim()}>
        {pending ? "Saving…" : submitLabel}
      </Button>
    </form>
  )
}
