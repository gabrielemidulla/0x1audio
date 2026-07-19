import { useState } from "react"
import { Navigate, useOutletContext } from "react-router"

import { api } from "~/lib/api"
import type { AppOutletContext } from "~/routes/_app"
import { Button } from "~/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "~/components/ui/card"
import { Input } from "~/components/ui/input"
import { Label } from "~/components/ui/label"
import { Skeleton } from "~/components/ui/skeleton"

export default function UsersPage() {
  const { user } = useOutletContext<AppOutletContext>()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [created, setCreated] = useState<string | null>(null)

  if (user && user.role !== "master") {
    return <Navigate to="/" replace />
  }

  return (
    <div className="flex max-w-md flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-medium tracking-tight">Users</h1>
        <p className="text-muted-foreground text-sm leading-relaxed">
          Public registration is closed. Create accounts for other people here.
        </p>
      </div>

      {!user ? (
        <Card>
          <CardHeader className="gap-2">
            <Skeleton className="h-5 w-28" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-64 max-w-full" />
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Skeleton className="h-4 w-12" />
              <Skeleton className="h-8 w-full" />
            </div>
            <div className="flex flex-col gap-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-8 w-full" />
            </div>
          </CardContent>
          <CardFooter>
            <Skeleton className="h-8 w-28" />
          </CardFooter>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Create user</CardTitle>
            <CardDescription>
              They sign in with this email and temporary password, then must choose
              a new password and display name on first login.
            </CardDescription>
          </CardHeader>
          <form
            className="flex flex-col gap-6"
            onSubmit={async (event) => {
              event.preventDefault()
              const form = new FormData(event.currentTarget)
              const email = String(form.get("email") ?? "")
              const password = String(form.get("password") ?? "")
              setPending(true)
              setError(null)
              setCreated(null)
              const { error: apiError, response } = await api.v1.createUser({
                body: { email, password },
              })
              setPending(false)
              if (apiError) {
                setError(
                  response?.status === 409
                    ? "Email already registered"
                    : "Could not create user",
                )
                return
              }
              setCreated(email)
              event.currentTarget.reset()
            }}
          >
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="new-email">Email</Label>
                <Input
                  id="new-email"
                  name="email"
                  type="email"
                  required
                  disabled={pending}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="new-password">Temporary password</Label>
                <Input
                  id="new-password"
                  name="password"
                  type="password"
                  minLength={8}
                  required
                  disabled={pending}
                />
              </div>
              {error ? <p className="text-destructive text-sm">{error}</p> : null}
              {created ? (
                <p className="text-muted-foreground text-sm">Created {created}</p>
              ) : null}
            </CardContent>
            <CardFooter>
              <Button type="submit" disabled={pending}>
                {pending ? "Creating…" : "Create user"}
              </Button>
            </CardFooter>
          </form>
        </Card>
      )}
    </div>
  )
}
