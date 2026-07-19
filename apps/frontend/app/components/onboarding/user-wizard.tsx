import { useMemo, useState } from "react"
import { useNavigate } from "react-router"
import { toast } from "sonner"

import {
  OnboardingShell,
  type OnboardingSlide,
} from "~/components/onboarding/shell"
import { ProfileStep } from "~/components/onboarding/profile-step"
import { PasswordRequirements } from "~/components/password-requirements"
import { Button } from "~/components/ui/button"
import { Input } from "~/components/ui/input"
import { Label } from "~/components/ui/label"
import { api } from "~/lib/api"
import { isPasswordStrong } from "~/components/password-requirements"

type UserOnboardingWizardProps = {
  demo?: boolean
  needsPassword?: boolean
  needsProfile?: boolean
}

export function UserOnboardingWizard({
  demo = false,
  needsPassword = true,
  needsProfile = true,
}: UserOnboardingWizardProps) {
  const navigate = useNavigate()

  const stepKinds = useMemo((): Array<"password" | "profile"> => {
    const list: Array<"password" | "profile"> = []
    if (needsPassword) list.push("password")
    if (needsProfile) list.push("profile")
    return list.length > 0 ? list : ["profile"]
  }, [needsPassword, needsProfile])

  const [index, setIndex] = useState(0)
  const [maxReached, setMaxReached] = useState(0)
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  /** Last password successfully saved this session; null until first save. */
  const [savedPassword, setSavedPassword] = useState<string | null>(null)

  const kind = stepKinds[Math.min(index, stepKinds.length - 1)] ?? "profile"
  const stepNumber = index + 1
  const passwordOk = isPasswordStrong(password)
  const profileIndex = stepKinds.indexOf("profile")
  const passwordUnchanged =
    savedPassword !== null && password === savedPassword && password === confirm

  function goTo(next: number) {
    setError(null)
    setIndex(next)
    setMaxReached((value) => Math.max(value, next))
  }

  function tryBack() {
    if (index <= 0 || pending) return
    goTo(index - 1)
  }

  function tryForward() {
    if (index >= stepKinds.length - 1 || pending) return
    if (kind === "password") {
      if (!passwordOk) {
        setError("Password does not meet the requirements")
        return
      }
      if (password !== confirm) {
        setError("Passwords do not match")
        return
      }
      // Already saved this exact password — just advance.
      if (passwordUnchanged) {
        goTo(index + 1)
        return
      }
      void submitPasswordAndAdvance()
      return
    }
    if (index + 1 <= maxReached) {
      goTo(index + 1)
      return
    }
    goTo(index + 1)
  }

  async function submitPasswordAndAdvance() {
    if (demo) {
      setSavedPassword(password)
      if (profileIndex >= 0) goTo(profileIndex)
      else toast.success("Demo complete — nothing was saved")
      return
    }
    setPending(true)
    const { error: apiError } = await api.v1.changePassword({
      body: {
        new_password: password,
        // After the first forced change, the API requires the current password.
        ...(savedPassword ? { current_password: savedPassword } : {}),
      },
    })
    setPending(false)
    if (apiError) {
      setError("Could not update password")
      return
    }
    setSavedPassword(password)
    toast.success(savedPassword ? "Password updated" : "Password saved")
    if (profileIndex >= 0) {
      goTo(profileIndex)
      return
    }
    void navigate("/")
  }

  const slides: OnboardingSlide[] = stepKinds.map((stepKind) => {
    if (stepKind === "password") {
      return {
        title: "Choose a new password",
        description:
          "Your temporary password must be replaced before you continue.",
        content: (
          <form
            className="flex flex-col gap-5 rounded-2xl border bg-card/80 p-6 shadow-lg backdrop-blur-sm"
            onSubmit={(event) => {
              event.preventDefault()
              void tryForward()
            }}
          >
            <div className="flex flex-col gap-2">
              <Label htmlFor="new-password">New password</Label>
              <Input
                id="new-password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                minLength={8}
                required
                disabled={pending}
                autoFocus={kind === "password"}
              />
              <PasswordRequirements password={password} className="pt-1" />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="confirm-password">Confirm password</Label>
              <Input
                id="confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                minLength={8}
                required
                disabled={pending}
              />
            </div>
            {error && kind === "password" ? (
              <p className="text-destructive text-sm">{error}</p>
            ) : null}
            <Button
              type="submit"
              className="w-full"
              disabled={pending || !passwordOk || password !== confirm}
            >
              {pending
                ? "Saving…"
                : savedPassword && !passwordUnchanged
                  ? "Update & continue"
                  : "Continue"}
            </Button>
          </form>
        ),
      }
    }

    return {
      title: "Make it yours",
      description: "Pick a display name and optional profile photo.",
      content: (
        <ProfileStep
          pending={pending}
          error={kind === "profile" ? error : null}
          submitLabel={demo ? "Finish (demo)" : "Continue"}
          autoFocus={kind === "profile"}
          onSubmit={async ({ displayName, avatarFile }) => {
            setError(null)
            if (demo) {
              toast.success("Demo complete — nothing was saved")
              return
            }
            setPending(true)
            const { error: profileError } = await api.v1.updateMe({
              body: { display_name: displayName },
            })
            if (profileError) {
              setPending(false)
              setError("Could not save display name")
              return
            }
            if (avatarFile) {
              const { error: avatarError } = await api.v1.updateMyAvatar({
                body: { file: avatarFile },
              })
              if (avatarError) {
                toast.error("Profile saved, but avatar upload failed")
              }
            }
            setPending(false)
            toast.success("You're all set")
            void navigate("/")
          }}
        />
      ),
    }
  })

  return (
    <OnboardingShell
      slides={slides}
      step={stepNumber}
      canBack={index > 0 && !pending}
      canForward={
        index < stepKinds.length - 1 &&
        !pending &&
        (kind === "password"
          ? passwordOk && password === confirm
          : index + 1 <= maxReached)
      }
      onBack={tryBack}
      onForward={tryForward}
    />
  )
}
