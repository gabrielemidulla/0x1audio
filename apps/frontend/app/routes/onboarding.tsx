import { useEffect, useState } from "react"
import { Navigate } from "react-router"

import { UserOnboardingWizard } from "~/components/onboarding"
import { FullPageSpinner } from "~/components/loading"
import { api, type UserOut } from "~/lib/api"

export default function OnboardingPage() {
  const [user, setUser] = useState<UserOut | null | undefined>(undefined)

  useEffect(() => {
    void api.v1.me().then(({ data, error }) => {
      setUser(error ? null : (data ?? null))
    })
  }, [])

  if (user === undefined) {
    return <FullPageSpinner />
  }

  if (user === null) {
    return <Navigate to="/login" replace />
  }

  const needsPassword = Boolean(user.must_change_password)
  const needsProfile = !user.display_name?.trim()

  if (!needsPassword && !needsProfile) {
    return <Navigate to="/" replace />
  }

  return (
    <UserOnboardingWizard
      needsPassword={needsPassword}
      needsProfile={needsProfile}
    />
  )
}
