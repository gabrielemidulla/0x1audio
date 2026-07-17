import type { Config } from "@react-router/dev/config"

export default {
  // Static CSR — served as static files (nginx / CDN), not SSR
  ssr: false,
} satisfies Config
