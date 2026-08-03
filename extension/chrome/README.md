# Ownix Capture — Chrome extension (MVP, issue #478)

A lightweight capture client: send the current tab, a right-clicked link, or
selected text to Ownix Intake (`POST /api/intake/message`).

## What's here

```
manifest.json     Manifest V3
popup.html/       Toolbar popup — reads the active tab, "Send to Ownix"
src/popup.ts
options.html/     Choose the Ownix host
src/options.ts
src/background.ts Service worker — context menu (page/link/selection)
src/api.ts        Fetch client for /api/intake/message
icons/            Placeholder icons (solid signal-orange squares) — swap for real artwork before shipping
```

Plain TypeScript + DOM APIs, no React/JSX build step — the popup and options
pages are a handful of elements each, so a bundler felt like more machinery
than the surface warrants for an MVP. `initPopup()`/`initOptions()` are
exported and take a `Document` (+ fakes for `popup.ts`), so they're unit-
tested directly under jsdom without loading the real extension.

## Auth (issue #479 — pairing required)

Every request goes out with a bearer token minted by pairing, never a raw
session cookie: **Settings → Chrome Extension** in the dashboard generates a
one-time, 5-minute pairing code; the extension's Options page redeems it for
an opaque token (`POST /api/extension/token`) and stores only that token.
`sendToOwnix()` refuses to send anything until a token is paired — there is
no cookie-based fallback. (An earlier revision tried `credentials: 'include'`
against the dashboard's `vig_session` cookie; that never actually worked,
since the cookie is `SameSite=Lax` and Lax cookies aren't sent on a
cross-origin `fetch()` from an extension-origin context — only pairing does.)

## Load-unpacked / dev install

1. `cd extension/chrome && npm install`
2. `npm run build` — compiles `src/*.ts` to `src/*.js` in place (no bundler;
   `manifest.json`/`popup.html`/`options.html` all reference `src/*.js`
   directly).
3. Open `chrome://extensions`, enable **Developer mode** (top right).
4. **Load unpacked** → select `extension/chrome/`.
5. Click the toolbar icon → **Options** (or right-click the extension icon →
   Options) → set the Ownix host (defaults to `https://app.leondev.xyz`; use
   `http://localhost:8000` for a local backend).
6. In the dashboard, go to **Settings → Chrome Extension** and generate a
   pairing code; paste it into the Options page's **Connect** field. Once
   paired, use the toolbar popup or right-click a page/link/selection.

## Tests

```
npm install
npm test
```

Covers: API-client payload construction (`buildIntakePayload`, host
storage, the POST itself), context-menu payload normalization
(`payloadForContextMenuClick`), and popup success/error states.
