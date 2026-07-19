import { useEffect, useState } from "react"
import { Navigate } from "react-router"

import { MasterOnboardingWizard } from "~/components/onboarding"
import { FullPageSpinner } from "~/components/loading"
import { api } from "~/lib/api"

export default function RegisterPage() {
  const [open, setOpen] = useState<boolean | null>(null)

  useEffect(() => {
    void api.v1.authStatus().then(({ data }) => {
      setOpen(data?.registration_open ?? false)
    })
  }, [])

  if (open === null) {
    return <FullPageSpinner />
  }

  if (!open) {
    return <Navigate to="/login" replace />
  }

  return <MasterOnboardingWizard />
}
