import type { Config } from 'tailwindcss';

// Console tokens — normative source: DESIGN.md frontmatter.
const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: '#0b0c0f',
        surface: '#14161a',
        raised: '#1c1f25',
        line: {
          DEFAULT: '#262a31',
          strong: '#343a44',
        },
        ink: '#f5f6f8',
        body: '#b3b9c4',
        muted: '#8a919e',
        signal: {
          DEFAULT: '#f6921e',
          bright: '#ffa83d',
          deep: '#b96a06',
        },
        contrasignal: {
          DEFAULT: '#94e6ee',
          bright: '#9ec9ff',
          deep: '#649ca1',
        },
        onsignal: '#16100a',
        status: {
          done: '#4ade80',
          'done-tint': '#122b1c',
          pending: '#eab308',
          'pending-tint': '#2b240e',
          processing: '#60a5fa',
          'processing-tint': '#14233b',
          enriching: '#a78bfa',
          'enriching-tint': '#221a3d',
          error: '#f87171',
          'error-tint': '#371717',
          cancelled: '#9aa1ad',
          'cancelled-tint': '#23262c',
        },
        type: {
          short: '#f6017d',
          long: '#ff0100',
          article: '#2dd4bf',
          repo: '#8957e5',
        },
        'telegram-blue': '#26A5E4',
        'telegram-ring': '#145b7d',
        // Google-connected state only (CONTEXT.md `Account affordance`) —
        // deliberate off-system brand hue; never a substitute for signal.
        google: '#4285F4',
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'system-ui', 'sans-serif'],
        mono: [
          'var(--font-jetbrains)',
          'ui-monospace',
          'SFMono-Regular',
          'monospace',
        ],
      },
      transitionTimingFunction: {
        'out-quart': 'cubic-bezier(0.25, 1, 0.5, 1)',
      },
      boxShadow: {
        // The one shadow in the system (DESIGN.md Plate Rule): overlays only.
        overlay:
          '0px 2px 4px rgba(0,0,0,0.4), 0px 12px 24px -8px rgba(0,0,0,0.5)',
      },
      animation: {
        'tooltip-in': 'tooltip-in 140ms ease-out both',
        'tooltip-out': 'tooltip-out 100ms ease-out both',
      },
    },
  },
  plugins: [],
};

export default config;
