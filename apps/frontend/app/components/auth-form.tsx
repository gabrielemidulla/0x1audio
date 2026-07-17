import type { ReactNode } from "react"

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

type AuthFormProps = {
  title: string
  description: string
  submitLabel: string
  error: string | null
  pending: boolean
  onSubmit: (email: string, password: string) => void | Promise<void>
  footer?: ReactNode
}

export function AuthForm({
  title,
  description,
  submitLabel,
  error,
  pending,
  onSubmit,
  footer,
}: AuthFormProps) {
  return (
    <div className="flex min-h-svh items-center justify-center p-6">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <form
          className="flex flex-col gap-6"
          onSubmit={(event) => {
            event.preventDefault()
            const form = new FormData(event.currentTarget)
            onSubmit(String(form.get("email") ?? ""), String(form.get("password") ?? ""))
          }}
        >
          <CardContent className="flex flex-col gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                disabled={pending}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                minLength={8}
                required
                disabled={pending}
              />
            </div>
            {error ? <p className="text-destructive text-sm">{error}</p> : null}
          </CardContent>
          <CardFooter className="flex flex-col gap-3">
            <Button type="submit" className="w-full" disabled={pending}>
              {pending ? "Please wait…" : submitLabel}
            </Button>
            {footer ? (
              <div className="text-muted-foreground text-center text-sm">{footer}</div>
            ) : null}
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}
