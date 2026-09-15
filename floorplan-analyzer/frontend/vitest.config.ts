import { defineConfig } from "vitest/config";
import { resolve } from "node:path";

export default defineConfig({
  esbuild: { jsx: "automatic" },
  // アプリ直下の test/ からも、フロントエンドの依存を共有する。
  resolve: { dedupe: ["react", "react-dom", "@testing-library/react", "vitest"] },
  server: { fs: { allow: [resolve(__dirname, "..")] } },
  test: { include: ["../test/**/frontend/**/*.test.{ts,tsx}"] },
});
