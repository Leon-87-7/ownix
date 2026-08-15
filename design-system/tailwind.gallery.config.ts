import type { Config } from 'tailwindcss';
// Inherit the app's real theme via preset — never re-declare token values here.
// The source of truth stays web/tailwind.config.ts (which mirrors DESIGN.md).
import base from '../web/tailwind.config';

export default {
  // `presets` pulls in the app's entire theme.extend (colors, fontSize, …) so
  // every `bg-canvas` / `text-signal` / `shadow-overlay` the gallery references
  // resolves to the exact value the app ships.
  presets: [base as Config],
  content: [
    './index.html',
    './_generated/safelist.html',
  ],
} satisfies Config;
