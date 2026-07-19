import { useEffect, useState } from "react"
import { Navigate, useNavigate } from "react-router"
import { toast } from "sonner"

import { AuthForm } from "~/components/auth-form"
import { FullPageSpinner } from "~/components/loading"
import { api } from "~/lib/api"

export default function LoginPage() {
  const navigate = useNavigate()
  const [registrationOpen, setRegistrationOpen] = useState<boolean | null>(null)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    void api.v1.authStatus().then(({ data }) => {
      setRegistrationOpen(data?.registration_open ?? false)
    })
  }, [])

  if (registrationOpen === null) {
    return <FullPageSpinner />
  }

  if (registrationOpen) {
    return <Navigate to="/register" replace />
  }

  return (
    <AuthForm
      submitLabel="Sign in"
      error={null}
      pending={pending}
      onSubmit={async (email, password) => {
        setPending(true)
        const { error: apiError } = await api.v1.login({ body: { email, password } })
        setPending(false)
        if (apiError) {
          toast.error("Invalid email or password")
          return
        }
        toast.success("Signed in")
        void navigate("/")
      }}
    />
  )
}
