import { defineConfig, OperationPath } from "@hey-api/openapi-ts"

export default defineConfig({
  input: "./openapi.json",
  output: "app/client",
  plugins: [
    {
      name: "@hey-api/client-fetch",
      runtimeConfigPath: "./app/hey-api.ts",
    },
    {
      name: "@hey-api/sdk",
      operations: {
        containerName: "Api",
        strategy: "single",
        // /api/v1/... → api.v1.<operationId>()
        nesting(operation) {
          const version =
            String(operation.path).match(/^\/api\/(v\d+)\b/)?.[1] ?? "v1"
          return [version, ...OperationPath.fromOperationId()(operation)]
        },
      },
    },
  ],
})
