# Ownix Capture — Chrome extension (MVP, issue #478)

A lightweight capture client: send the current tab, a right-clicked link, or
selected text to Ownix Intake (`POST /api/intake/message`).

## What's here

```
manifest.json     Manifest V3
popup.html/       Toolbar popup — reads the active tab, "Send to Ownix"
src/popup.ts
options.html/     Pair/disconnect this browser with Ownix
src/options.ts
src/background.ts Service worker — context menu (page/link/selection)
src/api.ts        Fetch client for /api/intake/message
icons/            Ownix brand-mark icons generated from web/app/opengraph-image.tsx
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

## Chrome Web Store reviewer access

Chrome reviewers need to exercise the dashboard pairing flow before the
extension is live, but they should not need Telegram. During the review window
only, enable the temporary reviewer login on the web app/API:

```dotenv
REVIEWER_LOGIN_ENABLED=true
REVIEWER_LOGIN_EMAIL=<reviewer email shown in Chrome Web Store test instructions>
REVIEWER_LOGIN_PASSWORD=<single-use review code>
NEXT_PUBLIC_REVIEWER_LOGIN_ENABLED=1
```

Set `NEXT_PUBLIC_REVIEWER_LOGIN_ENABLED` before building the web application,
then deploy that build so the reviewer form is included in the client bundle.
Give Chrome the email/code in **Test instructions** and tell them to sign in at
`/login`, then open **Settings → Chrome Extension**, generate a pairing code,
and paste it into the extension Options page. After the extension is approved
and live, disable `REVIEWER_LOGIN_ENABLED`, remove
`NEXT_PUBLIC_REVIEWER_LOGIN_ENABLED`, and remove or rotate
`REVIEWER_LOGIN_EMAIL` and `REVIEWER_LOGIN_PASSWORD` before the next production
deploy. Deploying with reviewer login disabled rejects existing reviewer
sessions as well as new `/reviewer-login` requests.

## Load-unpacked / dev install

1. `cd extension/chrome && npm install`
2. `npm run build` — compiles `src/*.ts` to `src/*.js` in place (no bundler;
   `manifest.json`/`popup.html`/`options.html` all reference `src/*.js`
   directly).
3. Open `chrome://extensions`, enable **Developer mode** (top right).
4. **Load unpacked** → select `extension/chrome/`.
5. In the dashboard, go to **Settings → Chrome Extension** and generate a
   pairing code; paste it into the Options page's **Connect** field. Once
   paired, use the toolbar popup or right-click a page/link/selection.

## Tests

```
npm install
npm test
```

Covers: API-client payload construction (`buildIntakePayload`, production
host validation, the POST itself), context-menu payload normalization
(`payloadForContextMenuClick`), options pairing, and popup success/error states.
