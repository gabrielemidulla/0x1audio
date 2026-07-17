export function greetingName(email: string): string {
  const local = email.split("@")[0] ?? email
  const part = local.split(/[._-]/)[0] ?? local
  if (!part) return email
  return part.charAt(0).toUpperCase() + part.slice(1)
}
