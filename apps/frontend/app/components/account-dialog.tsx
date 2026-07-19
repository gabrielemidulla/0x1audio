import { useEffect, useState } from "react"
import { User as UserIcon } from "@phosphor-icons/react"
import { toast } from "sonner"

import { Avatar, AvatarFallback, AvatarImage } from "~/components/ui/avatar"
import { Button } from "~/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "~/components/ui/dialog"
import { Input } from "~/components/ui/input"
import { Label } from "~/components/ui/label"
import { Separator } from "~/components/ui/separator"
import { PasswordRequirements, isPasswordStrong } from "~/components/password-requirements"
import { api, type UserOut, userAvatarUrl } from "~/lib/api"
import { ALLOWED_IMAGE_MIME_TYPES } from "~/client/constants.gen"

type AccountDialogProps = {
  user: UserOut
  open: boolean
  onOpenChange: (open: boolean) => void
  onUserChange: (user: UserOut) => void
}

export function AccountDialog({
  user,
  open,
  onOpenChange,
  onUserChange,
}: AccountDialogProps) {
  const [displayName, setDisplayName] = useState(user.display_name ?? "")
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null)
  const [avatarVersion, setAvatarVersion] = useState(0)
  const [pendingProfile, setPendingProfile] = useState(false)

  const [email, setEmail] = useState(user.email)
  const [emailPassword, setEmailPassword] = useState("")
  const [pendingEmail, setPendingEmail] = useState(false)

  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [pendingPassword, setPendingPassword] = useState(false)

  useEffect(() => {
    if (!open) return
    setDisplayName(user.display_name ?? "")
    setEmail(user.email)
    setEmailPassword("")
    setCurrentPassword("")
    setNewPassword("")
    setConfirmPassword("")
    setAvatarPreview(null)
  }, [open, user.display_name, user.email])

  const avatarSrc =
    avatarPreview ??
    (user.has_avatar ? userAvatarUrl(avatarVersion || user.id) : undefined)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Account</DialogTitle>
          <DialogDescription>
            Profile, email, and password for your 0x1audio account.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-6">
          <section className="flex flex-col gap-4">
            <div className="flex items-center gap-4">
              <label className="cursor-pointer">
                <Avatar className="size-16 data-[size=default]:size-16">
                  {avatarSrc ? <AvatarImage src={avatarSrc} alt="" /> : null}
                  <AvatarFallback>
                    <UserIcon className="size-6" />
                  </AvatarFallback>
                </Avatar>
                <input
                  type="file"
                  accept={ALLOWED_IMAGE_MIME_TYPES.join(",")}
                  className="sr-only"
                  onChange={async (event) => {
                    const file = event.target.files?.[0]
                    if (!file) return
                    const local = URL.createObjectURL(file)
                    setAvatarPreview(local)
                    const { data, error } = await api.v1.updateMyAvatar({
                      body: { file },
                    })
                    if (error || !data) {
                      toast.error("Could not upload photo")
                      setAvatarPreview(null)
                      return
                    }
                    onUserChange(data)
                    setAvatarVersion((value) => value + 1)
                    toast.success("Photo updated")
                  }}
                />
              </label>
              <div className="min-w-0 flex-1 space-y-1">
                <p className="truncate text-sm font-medium">
                  {user.display_name || "No display name"}
                </p>
                <p className="text-muted-foreground truncate text-xs">{user.email}</p>
                <p className="text-muted-foreground text-xs">Click photo to change</p>
              </div>
            </div>

            <form
              className="flex flex-col gap-3"
              onSubmit={async (event) => {
                event.preventDefault()
                const cleaned = displayName.trim()
                if (!cleaned) return
                setPendingProfile(true)
                const { data, error } = await api.v1.updateMe({
                  body: { display_name: cleaned },
                })
                setPendingProfile(false)
                if (error || !data) {
                  toast.error("Could not update display name")
                  return
                }
                onUserChange(data)
                toast.success("Display name updated")
              }}
            >
              <div className="flex flex-col gap-2">
                <Label htmlFor="account-display-name">Display name</Label>
                <Input
                  id="account-display-name"
                  value={displayName}
                  onChange={(event) => setDisplayName(event.target.value)}
                  maxLength={120}
                  required
                  disabled={pendingProfile}
                />
              </div>
              <Button type="submit" size="sm" disabled={pendingProfile}>
                {pendingProfile ? "Saving…" : "Save name"}
              </Button>
            </form>
          </section>

          <Separator />

          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-medium">Change email</h3>
            <form
              className="flex flex-col gap-3"
              onSubmit={async (event) => {
                event.preventDefault()
                setPendingEmail(true)
                const { data, error, response } = await api.v1.changeEmail({
                  body: {
                    current_password: emailPassword,
                    new_email: email.trim(),
                  },
                })
                setPendingEmail(false)
                if (error || !data) {
                  toast.error(
                    response?.status === 409
                      ? "Email already registered"
                      : "Could not change email",
                  )
                  return
                }
                onUserChange(data)
                setEmailPassword("")
                toast.success("Email updated")
              }}
            >
              <div className="flex flex-col gap-2">
                <Label htmlFor="account-email">New email</Label>
                <Input
                  id="account-email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  disabled={pendingEmail}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="account-email-password">Current password</Label>
                <Input
                  id="account-email-password"
                  type="password"
                  autoComplete="current-password"
                  value={emailPassword}
                  onChange={(event) => setEmailPassword(event.target.value)}
                  required
                  disabled={pendingEmail}
                />
              </div>
              <Button type="submit" size="sm" variant="secondary" disabled={pendingEmail}>
                {pendingEmail ? "Updating…" : "Update email"}
              </Button>
            </form>
          </section>

          <Separator />

          <section className="flex flex-col gap-3">
            <h3 className="text-sm font-medium">Change password</h3>
            <form
              className="flex flex-col gap-3"
              onSubmit={async (event) => {
                event.preventDefault()
                if (!isPasswordStrong(newPassword)) {
                  toast.error("Password does not meet the requirements")
                  return
                }
                if (newPassword !== confirmPassword) {
                  toast.error("Passwords do not match")
                  return
                }
                setPendingPassword(true)
                const { data, error } = await api.v1.changePassword({
                  body: {
                    current_password: currentPassword,
                    new_password: newPassword,
                  },
                })
                setPendingPassword(false)
                if (error || !data) {
                  toast.error("Could not change password")
                  return
                }
                onUserChange(data)
                setCurrentPassword("")
                setNewPassword("")
                setConfirmPassword("")
                toast.success("Password updated")
              }}
            >
              <div className="flex flex-col gap-2">
                <Label htmlFor="account-current-password">Current password</Label>
                <Input
                  id="account-current-password"
                  type="password"
                  autoComplete="current-password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  required
                  disabled={pendingPassword}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="account-new-password">New password</Label>
                <Input
                  id="account-new-password"
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  minLength={8}
                  required
                  disabled={pendingPassword}
                />
                <PasswordRequirements password={newPassword} className="pt-1" />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="account-confirm-password">Confirm new password</Label>
                <Input
                  id="account-confirm-password"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  minLength={8}
                  required
                  disabled={pendingPassword}
                />
              </div>
              <Button
                type="submit"
                size="sm"
                variant="secondary"
                disabled={
                  pendingPassword ||
                  !isPasswordStrong(newPassword) ||
                  newPassword !== confirmPassword
                }
              >
                {pendingPassword ? "Updating…" : "Update password"}
              </Button>
            </form>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  )
}
