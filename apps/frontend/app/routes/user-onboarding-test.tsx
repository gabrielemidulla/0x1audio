import { Navigate } from "react-router"

import { UserOnboardingWizard } from "~/components/onboarding"

export default function UserOnboardingTestPage() {
  if (!import.meta.env.DEV) {
    return <Navigate to="/" replace />
  }

  return (
    <UserOnboardingWizard demo needsPassword={true} needsProfile={true} />
  )
}
