import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
  {
    // React Compiler diagnostics, newly bundled into eslint-config-next's
    // core-web-vitals as of Next 16 — not part of #366's scope (keep the
    // @next/next plugin active), and pre-existing code across ~25 files
    // predates this discipline. Downgraded to warn rather than silenced, so
    // they stay visible for a dedicated follow-up instead of gating this
    // upgrade on an unscoped effect-by-effect rewrite.
    rules: {
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/immutability": "warn",
      "react-hooks/static-components": "warn",
    },
  },
]);
