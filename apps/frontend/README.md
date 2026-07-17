# Frontend

React Router static (SPA) app with shadcn/ui. Typed API client via `@hey-api/openapi-ts`.

**Package manager: pnpm**

```bash
cd apps/frontend
pnpm install
pnpm dev
pnpm build
```

Or via Compose (hot reload):

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build frontend
```

Regenerate the API client after backend OpenAPI changes:

```bash
curl -s http://127.0.0.1:8000/openapi.json -o openapi.json
pnpm generate:api
```

SDK nesting is configured in `openapi-ts.config.ts` (`Api` + `/api/v1` → `api.v1.<operationId>`). After codegen, use:

```ts
import { api } from "~/lib/api"

await api.v1.me()
await api.v1.login({ body: { email, password } })
```

Add shadcn components:

```bash
pnpm dlx shadcn@latest add <component>
```

See [docs/SPEC.md](../../docs/SPEC.md).
