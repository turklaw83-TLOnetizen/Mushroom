import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    exclude: ["tests/e2e/**"],
    coverage: {
      provider: "v8",
      include: ["lib/**/*.ts", "hooks/**/*.ts", "hooks/**/*.tsx"],
      exclude: [
        "app/**/page.tsx",
        "app/**/layout.tsx",
        "components/**/*.tsx",
        "node_modules/**",
      ],
    },
  },
});
