// Ownix Design System — gallery build step.
//
// Run with:  npx tsx design-system/build.mjs   (tsx is needed to import the
// app's TypeScript Tailwind config directly — we read token *names* from the
// real source and never re-type token *values*.)
//
// Produces, all under design-system/_generated/:
//   app.css      the app's REAL compiled Tailwind CSS (via the tailwind CLI)
//   manifest.json  build metadata + token name lists + component @ds blocks
// and regenerates design-system/index.html (Tokens section) with literal token
// classes, so the gallery reads every value live via getComputedStyle.
//
// Nothing here hard-codes a hex/size value. Change a token in
// web/tailwind.config.ts (mirroring DESIGN.md) and re-run: the gallery updates.

import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync, readdirSync, statSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative, sep } from 'node:path';
import * as cfgMod from '../web/tailwind.config.ts';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, '..');
const GEN = join(HERE, '_generated');
mkdirSync(GEN, { recursive: true });

// tsx/esm interop double-wraps the default export; unwrap defensively.
const cfg = cfgMod.default?.default ?? cfgMod.default ?? cfgMod;
const ext = cfg.theme.extend;

// ---- token enumeration (names only; values come from the compiled CSS) ------
function flattenColors(colors) {
  const out = [];
  for (const [k, v] of Object.entries(colors)) {
    if (typeof v === 'string') out.push(k);
    else for (const sub of Object.keys(v)) out.push(sub === 'DEFAULT' ? k : `${k}-${sub}`);
  }
  return out;
}
const colorTokens = flattenColors(ext.colors);
const fontSizeTokens = Object.entries(ext.fontSize).map(([name, val]) => ({ name, rem: val }));
const fontFamilyTokens = Object.keys(ext.fontFamily);
const shadowTokens = Object.keys(ext.boxShadow);
// Radii are Tailwind defaults (DESIGN.md prescribes 4/6/8/12; config does not
// override — see _inventory/drift.md §3.D). Show the DESIGN.md-relevant rungs;
// their live values are read from the compiled CSS, so any future override shows.
const radiusTokens = ['none', 'sm', 'md', 'lg', 'xl', 'full'];

// ---- component @ds block scan (Phase 2 rationale; empty until authored) ------
function walk(dir) {
  const out = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(p));
    else if (e.name.endsWith('.tsx') && !e.name.endsWith('.test.tsx')) out.push(p);
  }
  return out;
}
function parseDs(src) {
  const m = src.match(/\/\*\s*@ds\b([\s\S]*?)\*\//);
  return m ? m[1].trim() : null;
}
const componentFiles = walk(join(REPO, 'web', 'components'));
const components = [];
for (const f of componentFiles) {
  const src = readFileSync(f, 'utf8');
  const ds = parseDs(src);
  // Normalize to forward slashes: this repo is worked on from both POSIX and
  // Windows sessions, and manifest paths should be stable across both.
  const rel = relative(REPO, f).split(sep).join('/');
  const hash = createHash('sha256').update(src).digest('hex').slice(0, 12);
  if (ds) components.push({ file: rel, hash, ds });
}

// ---- build metadata ---------------------------------------------------------
let sha = 'unknown';
try { sha = execFileSync('git', ['rev-parse', '--short', 'HEAD'], { cwd: REPO }).toString().trim(); } catch {}
const builtAt = new Date().toISOString();

const manifest = {
  builtAt,
  sha,
  tokenSource: 'DESIGN.md frontmatter -> web/tailwind.config.ts',
  tokens: {
    colors: colorTokens,
    fontSize: fontSizeTokens,
    fontFamily: fontFamilyTokens,
    boxShadow: shadowTokens,
    radius: radiusTokens,
  },
  componentCount: componentFiles.length,
  componentsWithDs: components.length,
  components,
};
writeFileSync(join(GEN, 'manifest.json'), JSON.stringify(manifest, null, 2));

// ---- index.html generation --------------------------------------------------
// Swatch/specimen elements carry LITERAL token classes so Tailwind compiles
// them and getComputedStyle reads the shipped value.
const colorSwatch = (t) => `
  <div class="rounded-md overflow-hidden border border-line bg-surface">
    <div class="h-16 bg-${t}" data-token="${t}" data-prop="backgroundColor"></div>
    <div class="px-3 py-2">
      <div class="font-mono text-mono-label text-ink">${t}</div>
      <div class="font-mono text-micro text-muted" data-value-for="${t}">…</div>
    </div>
  </div>`;

const typeSpecimen = (t) => `
  <div class="flex items-baseline gap-4 border-b border-line py-3">
    <div class="text-${t.name} text-ink truncate" data-token="${t.name}" data-prop="fontSize">Second Brain</div>
    <div class="ml-auto text-right shrink-0">
      <div class="font-mono text-mono-label text-body">text-${t.name}</div>
      <div class="font-mono text-micro text-muted"><span data-value-for="${t.name}">…</span> · ${t.rem}</div>
    </div>
  </div>`;

const fontSpecimen = (f) => `
  <div class="border border-line rounded-md p-4 bg-surface">
    <div class="font-${f} text-headline text-ink">Aa Bb Cc 0123</div>
    <div class="font-mono text-mono-label text-muted mt-2">font-${f}</div>
  </div>`;

const radiusChip = (r) => `
  <div class="flex flex-col items-center gap-2">
    <div class="w-16 h-16 bg-raised border border-line rounded-${r}" data-token="rounded-${r}" data-prop="borderRadius"></div>
    <div class="font-mono text-micro text-muted">rounded-${r}</div>
  </div>`;

const colorsHtml = colorTokens.map(colorSwatch).join('');
const typeHtml = fontSizeTokens.map(typeSpecimen).join('');
const fontsHtml = fontFamilyTokens.map(fontSpecimen).join('');
const radiiHtml = radiusTokens.map(radiusChip).join('');

const html = `<!doctype html>
<html lang="en" class="bg-canvas">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Ownix Design System</title>
<link rel="stylesheet" href="./_generated/app.css" />
</head>
<body class="bg-canvas text-body font-sans">
<div class="mx-auto max-w-6xl px-6 py-10">
  <header class="mb-10">
    <h1 class="text-display text-ink font-sans">Ownix Design System</h1>
    <p class="text-copy text-body mt-2 max-w-2xl">Every value on this page is read live from the app's compiled Tailwind CSS. The label is the token name; the value beside it is whatever the app currently ships. Nothing here is hand-typed — re-run <code class="font-mono text-mono-label text-signal">npx tsx design-system/build.mjs</code> after a token change and the page updates.</p>
    <div class="font-mono text-mono-label text-muted mt-3">build ${sha} · ${builtAt} · source: DESIGN.md → tailwind.config.ts</div>
  </header>

  <nav class="font-mono text-mono-label flex flex-wrap gap-x-4 gap-y-1 border-y border-line py-3 mb-10">
    <a class="text-signal hover:text-signal-bright" href="#colors">colors</a>
    <a class="text-signal hover:text-signal-bright" href="#type">type scale</a>
    <a class="text-signal hover:text-signal-bright" href="#fonts">fonts</a>
    <a class="text-signal hover:text-signal-bright" href="#radii">radii</a>
    <a class="text-signal hover:text-signal-bright" href="#shadow">shadow</a>
    <a class="text-muted" href="#components">components (pending)</a>
  </nav>

  <section id="colors" class="mb-14">
    <h2 class="text-headline text-ink mb-4">Colors <span class="font-mono text-mono-label text-muted">${colorTokens.length} tokens</span></h2>
    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">${colorsHtml}</div>
  </section>

  <section id="type" class="mb-14">
    <h2 class="text-headline text-ink mb-4">Type scale <span class="font-mono text-mono-label text-muted">${fontSizeTokens.length} sizes</span></h2>
    <div>${typeHtml}</div>
  </section>

  <section id="fonts" class="mb-14">
    <h2 class="text-headline text-ink mb-4">Font families</h2>
    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">${fontsHtml}</div>
  </section>

  <section id="radii" class="mb-14">
    <h2 class="text-headline text-ink mb-4">Radii</h2>
    <div class="flex flex-wrap gap-6">${radiiHtml}</div>
  </section>

  <section id="shadow" class="mb-14">
    <h2 class="text-headline text-ink mb-4">Shadow <span class="font-mono text-mono-label text-muted">overlays only</span></h2>
    <div class="w-48 h-24 bg-raised rounded-lg shadow-overlay grid place-items-center font-mono text-mono-label text-body">shadow-overlay</div>
  </section>

  <section id="components" class="mb-14">
    <h2 class="text-headline text-ink mb-4">Components</h2>
    <div class="border border-line rounded-md p-5 bg-surface">
      <div class="font-mono text-mono-label text-signal mb-2">pending an architecture decision</div>
      <p class="text-copy text-body max-w-2xl">The Tokens layer above is fully live. The component gallery needs a rendering strategy that shows the <em>real</em> React components without copying their markup (handoff §0). That decision is open — see <code class="font-mono text-mono-label text-ink">design-system/README.md</code>.</p>
    </div>
  </section>
</div>

<script>
  // Live-read: replace each token's placeholder with its shipped computed value.
  function toHex(rgb) {
    const m = rgb && rgb.match(/rgba?\\(([^)]+)\\)/);
    if (!m) return rgb || '';
    const [r,g,b] = m[1].split(',').map(n => parseInt(n,10));
    if ([r,g,b].some(Number.isNaN)) return rgb;
    return '#' + [r,g,b].map(n => n.toString(16).padStart(2,'0')).join('');
  }
  document.querySelectorAll('[data-token][data-prop]').forEach(el => {
    const name = el.getAttribute('data-token');
    const prop = el.getAttribute('data-prop');
    const cs = getComputedStyle(el);
    let val = cs[prop];
    if (prop === 'backgroundColor') val = toHex(val);
    if (prop === 'fontSize') val = val; // px
    const target = document.querySelector('[data-value-for="' + CSS.escape(name) + '"]');
    if (target) target.textContent = val;
    if (prop === 'borderRadius') {
      // radii show value inline under the chip label already; annotate title
      el.title = name + ' = ' + val;
    }
  });
  // Build metadata is injected server-side (above) so this page works from
  // file:// — fetch() of a local file is blocked by the file:// origin.
</script>
</body>
</html>`;
writeFileSync(join(HERE, 'index.html'), html);

// ---- compile the app's real CSS (scans the index.html we just wrote) ---------
console.log('Compiling app CSS via tailwind CLI…');
// npx is a .cmd shim on Windows, so it needs shell:true there; execFileSync
// on POSIX runs the binary directly and shell:true is harmless either way.
execFileSync('npx', [
  '--yes', 'tailwindcss@3',
  '-c', join(HERE, 'tailwind.gallery.config.ts'),
  '-i', join(REPO, 'web', 'app', 'globals.css'),
  '-o', join(GEN, 'app.css'),
  '--minify',
], { cwd: HERE, stdio: 'inherit', shell: process.platform === 'win32' });

console.log(`\nDone. ${colorTokens.length} colors, ${fontSizeTokens.length} sizes, ` +
  `${componentFiles.length} components (${components.length} with @ds).`);
console.log('Open design-system/index.html (file:// is fine).');
