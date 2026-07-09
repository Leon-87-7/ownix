import type { Config } from 'tailwindcss';

// Ownix tokens — normative source: DESIGN.md frontmatter.
const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: '#0d0e10',
        surface: '#16181c',
        raised: '#202329',
        line: {
          DEFAULT: '#30343d',
          strong: '#343a44',
        },
        ink: '#f4f1eb',
        body: '#c6c1b8',
        muted: '#948e84',
        signal: {
          DEFAULT: '#d99a45',
          bright: '#efb566',
          deep: '#a57534',
        },
        contrasignal: {
          DEFAULT: '#94e6ee',
          bright: '#9ec9ff',
          deep: '#649ca1',
        },
        onsignal: '#1b1309',
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
          short: '#c084fc',
          long: '#38bdf8',
          article: '#2dd4bf',
          repo: '#fb7185',
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
