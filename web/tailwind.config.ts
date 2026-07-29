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
      // Type scale in rem, so text honours the reader's browser font-size
      // setting — `px` font sizes silently ignore it. Named by the role
      // DESIGN.md already defines, never by value: `text-[0.8125rem]` is just
      // `text-[13px]` wearing a different hat.
      //
      // Deliberately bare strings, not [size, { lineHeight }] tuples. A tuple
      // makes every `text-*` utility also emit a line-height, which would
      // silently restyle ~124 existing call sites that currently inherit
      // theirs. Bare strings set font-size only, so this migration is a pure
      // unit change with no visual delta.
      //
      // None of these names may collide with a `colors` key — Tailwind would
      // emit two different `.text-<name>` rules. (Hence `copy` for DESIGN.md's
      // 14px Body role: `text-body` is already the body *colour*.)
      fontSize: {
        micro: '0.625rem', // 10px — dense table / chip text
        'mono-label': '0.6875rem', // 11px — DESIGN.md Mono Label
        label: '0.75rem', // 12px — DESIGN.md Label + Mono Meta
        button: '0.8125rem', // 13px — DESIGN.md Button
        copy: '0.875rem', // 14px — DESIGN.md Body
        prose: '0.9375rem', // 15px — landing section body
        title: '1rem', // 16px — DESIGN.md Title
        lead: '1.0625rem', // 17px — landing closing line
        stat: '1.75rem', // 28px — DESIGN.md Stat Value
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
        'slide-up-in': 'slide-up-in 180ms ease-out both',
        'slide-up-out': 'slide-up-out 140ms ease-out both',
      },
    },
  },
  plugins: [],
};

export default config;
