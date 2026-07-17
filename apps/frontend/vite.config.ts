import path from "node:path"
import { fileURLToPath } from "node:url"

import { reactRouter } from "@react-router/dev/vite"
import tailwindcss from "@tailwindcss/vite"
import { defineConfig } from "vite"

const inDocker = process.env.DOCKER === "1"
const apiTarget = inDocker ? "http://backend:8000" : "http://127.0.0.1:8000"
const root = fileURLToPath(new URL(".", import.meta.url))

export default defineConfig({
  resolve: {
    tsconfigPaths: true,
    // One Three/R3F instance — duplicate copies break Canvas context (Billboard hooks).
    dedupe: [
      "three",
      "@react-three/fiber",
      "@react-three/drei",
      "react",
      "react-dom",
    ],
    alias: {
      three: path.resolve(root, "node_modules/three"),
      "@react-three/fiber": path.resolve(
        root,
        "node_modules/@react-three/fiber",
      ),
    },
  },
  plugins: [tailwindcss(), reactRouter()],
  optimizeDeps: {
    // Prebundle reagraph (pulls graphology/events) so CJS EventEmitter interop works.
    include: ["three", "@react-three/fiber", "reagraph"],
  },
  server: {
    host: true,
    watch: inDocker ? { usePolling: true, interval: 300 } : undefined,
    // Same-origin /api so LAN clients don't need a hardcoded host IP.
    proxy: {
      "/api": { target: apiTarget, changeOrigin: true },
    },
  },
})
