import { Navigate } from "react-router"

import { MasterOnboardingWizard } from "~/components/onboarding"

export default function MasterOnboardingTestPage() {
  if (!import.meta.env.DEV) {
    return <Navigate to="/" replace />
  }

  return <MasterOnboardingWizard demo />
}
