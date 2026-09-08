import type { Config } from 'tailwindcss';

// Ownix tokens — normative source: DESIGN.md frontmatter.
const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: '#0d0e10',
        canvasb: '#0d0e17',
        surface: '#16181c',
        raised: '#202329',
        // A fourth rung on the plate ladder, one step above `raised`, reserved
        // for *selection* — a state that must not read as a hovered `raised`
        // plate and must not spend signal (DESIGN.md §5 "Chips", stepper
        // carve-out). Not a general-purpose surface.
        selected: '#2a2e36',
        line: {
          DEFAULT: '#30343d',
          strong: '#343a44',
        },
        ink: '#e6e6e6',
        body: '#b8b8b8',
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
        // Landing-only voices, see DESIGN.md two-voice system for the dashboard.
        title: ['var(--font-montserrat)', 'system-ui', 'sans-serif'],
        subtitle: ['var(--font-merienda)', 'Georgia', 'serif'],
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
        headline: '1.25rem', // 20px — DESIGN.md Headline
        stat: '1.75rem', // 28px — DESIGN.md Stat Value
        display: '1.5rem', // 24px — DESIGN.md Display
      },
      // Tracking is size-specific (DESIGN.md §4 Motion / apple-design skill
      // §15): negative on large display text, ~0 through body/UI sizes,
      // slightly positive on the smallest dense text. Keyed to the same
      // fontSize role names above — pair `text-stat` with `tracking-stat`.
      letterSpacing: {
        micro: '0.01em',
        'mono-label': '0.01em',
        label: '0',
        button: '0',
        copy: '0',
        prose: '0',
        title: '0',
        lead: '-0.005em',
        headline: '-0.01em',
        stat: '-0.02em',
        display: '-0.02em',
      },
      transitionTimingFunction: {
        'out-quart': 'cubic-bezier(0.25, 1, 0.5, 1)',
        // Reserved for moments a user's own gesture directly drove (DESIGN.md
        // §4 Motion) — a press-release or selection fill, never programmatic
        // fade-ins. Not used by default anywhere.
        spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      boxShadow: {
        // The one shadow in the system (DESIGN.md Plate Rule): overlays only.
        overlay:
          '0px 2px 4px rgba(0,0,0,0.4), 0px 12px 24px -8px rgba(0,0,0,0.5)',
      },
      animation: {
        'tooltip-in': 'tooltip-in 140ms ease-out both',
        'tooltip-out': 'tooltip-out 100ms ease-out both',
        // Overlay content surfaces (dialog/tooltip/dropdown): fade + scale
        // together, critically damped — no overshoot, this is programmatic
        // materialize-in, not a gesture the user drove (DESIGN.md §4 Motion).
        'material-in': 'material-in 160ms cubic-bezier(0.25, 1, 0.5, 1) both',
        'material-out': 'material-out 120ms cubic-bezier(0.25, 1, 0.5, 1) both',
        // Sheets get the skill's own drawer/sheet table entry (damping ~0.8):
        // a small overshoot on arrival earns it because a sheet's whole
        // presentation is a direct, physical response to the trigger tap —
        // exit stays critically damped, unchanged below.
        'slide-up-in': 'slide-up-in 220ms cubic-bezier(0.34, 1.56, 0.64, 1) both',
        'slide-up-out': 'slide-up-out 140ms ease-out both',
      },
    },
  },
  plugins: [],
};

export default config;
