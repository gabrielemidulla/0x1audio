import { useEffect, useState } from "react"
import { Navigate, useNavigate } from "react-router"

import { AuthForm } from "~/components/auth-form"
import { api } from "~/lib/api"

export default function RegisterPage() {
  const navigate = useNavigate()
  const [open, setOpen] = useState<boolean | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  useEffect(() => {
    void api.v1.authStatus().then(({ data }) => {
      setOpen(data?.registration_open ?? false)
    })
  }, [])

  if (open === null) {
    return (
      <main className="flex min-h-svh items-center justify-center p-6">
        <p className="text-muted-foreground text-sm">Loading…</p>
      </main>
    )
  }

  if (!open) {
    return <Navigate to="/login" replace />
  }

  return (
    <AuthForm
      title="Set up Tunelink"
      description="Create the master account. Public registration stays closed after this — only this account can add users later."
      submitLabel="Create master account"
      error={error}
      pending={pending}
      onSubmit={async (email, password) => {
        setPending(true)
        setError(null)
        const { error: apiError, response } = await api.v1.register({
          body: { email, password },
        })
        setPending(false)
        if (apiError) {
          setError(
            response?.status === 403
              ? "Registration is closed"
              : "Could not create account"
          )
          return
        }
        void navigate("/")
      }}
    />
  )
}
