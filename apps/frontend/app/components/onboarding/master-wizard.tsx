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

type MasterOnboardingWizardProps = {
  demo?: boolean
}

export function MasterOnboardingWizard({ demo = false }: MasterOnboardingWizardProps) {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [maxReached, setMaxReached] = useState(1)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const passwordOk = isPasswordStrong(password)

  function goTo(next: number) {
    setError(null)
    setStep(next)
    setMaxReached((value) => Math.max(value, next))
  }

  function validateStep(current: number): string | null {
    if (current === 1) {
      if (!email.trim()) return "Email is required"
      return null
    }
    if (current === 2) {
      if (!passwordOk) return "Password does not meet the requirements"
      if (password !== confirm) return "Passwords do not match"
      return null
    }
    return null
  }

  function tryForward() {
    if (step >= 3) return
    if (step + 1 <= maxReached) {
      goTo(step + 1)
      return
    }
    const message = validateStep(step)
    if (message) {
      setError(message)
      return
    }
    goTo(step + 1)
  }

  function tryBack() {
    if (step <= 1) return
    goTo(step - 1)
  }

  const slides: OnboardingSlide[] = [
    {
      title: "Your email",
      description: "This becomes the master account for 0x1audio.",
      content: (
        <form
          className="flex flex-col gap-5 rounded-2xl border bg-card/80 p-6 shadow-lg backdrop-blur-sm"
          onSubmit={(event) => {
            event.preventDefault()
            tryForward()
          }}
        >
          <div className="flex flex-col gap-2">
            <Label htmlFor="onboard-email">Email</Label>
            <Input
              id="onboard-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              autoFocus={step === 1}
            />
          </div>
          {error && step === 1 ? (
            <p className="text-destructive text-sm">{error}</p>
          ) : null}
          <Button type="submit" className="w-full">
            Continue
          </Button>
        </form>
      ),
    },
    {
      title: "Create a password",
      description: "Choose a strong password you’ll use to sign in.",
      content: (
        <form
          className="flex flex-col gap-5 rounded-2xl border bg-card/80 p-6 shadow-lg backdrop-blur-sm"
          onSubmit={(event) => {
            event.preventDefault()
            tryForward()
          }}
        >
          <div className="flex flex-col gap-2">
            <Label htmlFor="onboard-password">Password</Label>
            <Input
              id="onboard-password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={8}
              required
              autoFocus={step === 2}
            />
            <PasswordRequirements password={password} className="pt-1" />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="onboard-confirm">Confirm password</Label>
            <Input
              id="onboard-confirm"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              minLength={8}
              required
            />
          </div>
          {error && step === 2 ? (
            <p className="text-destructive text-sm">{error}</p>
          ) : null}
          <Button
            type="submit"
            className="w-full"
            disabled={!passwordOk || password !== confirm}
          >
            Continue
          </Button>
        </form>
      ),
    },
    {
      title: "Make it yours",
      description: "Pick a display name and optional profile photo.",
      content: (
        <ProfileStep
          pending={pending}
          error={step === 3 ? error : null}
          submitLabel={demo ? "Finish (demo)" : "Create account"}
          autoFocus={step === 3}
          onSubmit={async ({ displayName, avatarFile }) => {
            setError(null)
            if (demo) {
              toast.success("Demo complete — nothing was saved")
              return
            }
            setPending(true)
            const { error: registerError, response } = await api.v1.register({
              body: {
                email,
                password,
                display_name: displayName,
              },
            })
            if (registerError) {
              setPending(false)
              setError(
                response?.status === 403
                  ? "Registration is closed"
                  : "Could not create account",
              )
              return
            }
            if (avatarFile) {
              const { error: avatarError } = await api.v1.updateMyAvatar({
                body: { file: avatarFile },
              })
              if (avatarError) {
                toast.error("Account created, but avatar upload failed")
              }
            }
            setPending(false)
            toast.success("Welcome to 0x1audio")
            void navigate("/")
          }}
        />
      ),
    },
  ]

  return (
    <OnboardingShell
      slides={slides}
      step={step}
      canBack={step > 1 && !pending}
      canForward={step < slides.length && !pending}
      onBack={tryBack}
      onForward={tryForward}
    />
  )
}
