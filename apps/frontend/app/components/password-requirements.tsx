import { Check, X } from "@phosphor-icons/react"

import { PASSWORD } from "~/client/constants.gen"
import { cn } from "~/lib/utils"

type PasswordRequirementsProps = {
  password: string
  className?: string
}

type PasswordRuleKind = (typeof PASSWORD.rules)[number]["kind"]

function passwordRulePasses(kind: PasswordRuleKind, password: string): boolean {
  switch (kind) {
    case "min_length":
      return password.length >= PASSWORD.minLength
    case "has_upper":
      return /[A-Z]/.test(password)
    case "has_lower":
      return /[a-z]/.test(password)
    case "has_digit":
      return /\d/.test(password)
    case "has_special":
      return /[^A-Za-z0-9]/.test(password)
    default: {
      const _exhaustive: never = kind
      return _exhaustive
    }
  }
}

export function isPasswordStrong(password: string): boolean {
  return PASSWORD.rules.every((rule) => passwordRulePasses(rule.kind, password))
}

export function PasswordRequirements({
  password,
  className,
}: PasswordRequirementsProps) {
  const results = PASSWORD.rules.map((rule) => ({
    ...rule,
    ok: passwordRulePasses(rule.kind, password),
  }))

  return (
    <ul className={cn("flex flex-col gap-1.5", className)}>
      {results.map((rule) => (
        <li
          key={rule.id}
          className={cn(
            "flex items-center gap-2 text-xs",
            rule.ok
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-muted-foreground",
          )}
        >
          {rule.ok ? (
            <Check className="size-3.5 shrink-0" weight="bold" aria-hidden />
          ) : (
            <X className="size-3.5 shrink-0" weight="bold" aria-hidden />
          )}
          <span>{rule.label}</span>
        </li>
      ))}
    </ul>
  )
}
