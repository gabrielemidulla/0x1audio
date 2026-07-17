import { useEffect, useState } from "react"
import { Navigate, useNavigate } from "react-router"

import { AuthForm } from "~/components/auth-form"
import { api } from "~/lib/api"

export default function LoginPage() {
  const navigate = useNavigate()
  const [registrationOpen, setRegistrationOpen] = useState<boolean | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    void api.v1.authStatus().then(({ data }) => {
      setRegistrationOpen(data?.registration_open ?? false)
    })
  }, [])

  if (registrationOpen === null) {
    return (
      <main className="flex min-h-svh items-center justify-center p-6">
        <p className="text-muted-foreground text-sm">Loading…</p>
      </main>
    )
  }

  if (registrationOpen) {
    return <Navigate to="/register" replace />
  }

  return (
    <AuthForm
      title="Sign in"
      description="Email and password for your Tunelink account."
      submitLabel="Sign in"
      error={error}
      pending={pending}
      onSubmit={async (email, password) => {
        setPending(true)
        setError(null)
        const { error: apiError } = await api.v1.login({ body: { email, password } })
        setPending(false)
        if (apiError) {
          setError("Invalid email or password")
          return
        }
        void navigate("/")
      }}
    />
  )
}
