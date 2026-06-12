import type { Config } from "tailwindcss";

// Console tokens — normative source: DESIGN.md frontmatter.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#0b0c0f",
        surface: "#14161a",
        raised: "#1c1f25",
        line: {
          DEFAULT: "#262a31",
          strong: "#343a44",
        },
        ink: "#f5f6f8",
        body: "#b3b9c4",
        muted: "#8a919e",
        signal: {
          DEFAULT: "#f6921e",
          bright: "#ffa83d",
          deep: "#b96a06",
        },
        onsignal: "#16100a",
        status: {
          done: "#4ade80",
          "done-tint": "#122b1c",
          pending: "#eab308",
          "pending-tint": "#2b240e",
          processing: "#60a5fa",
          "processing-tint": "#14233b",
          enriching: "#a78bfa",
          "enriching-tint": "#221a3d",
          error: "#f87171",
          "error-tint": "#371717",
          cancelled: "#9aa1ad",
          "cancelled-tint": "#23262c",
        },
        type: {
          short: "#c084fc",
          long: "#38bdf8",
          article: "#2dd4bf",
          repo: "#fb7185",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      transitionTimingFunction: {
        "out-quart": "cubic-bezier(0.25, 1, 0.5, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
