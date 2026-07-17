import type { CreateClientConfig } from "~/client/client.gen"

export const createClientConfig: CreateClientConfig = (config) => ({
  ...config,
  // Empty/default → same-origin (Vite proxies /api → backend). Works on LAN.
  baseUrl: import.meta.env.VITE_API_BASE_URL || "",
  credentials: "include",
})
