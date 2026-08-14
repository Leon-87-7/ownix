# Chrome extension — shipping an update

Runbook for pushing a new version of **Ownix Capture** (`extension/chrome/`)
live on the Chrome Web Store. The extension is already published — item ID
`nofmlngkebkapkpjjiieppamfoodkfid` (linked from `web/app/page.tsx`). This
covers _updates_ to that existing listing, not a first-time submission.

## 1. Bump the version

Chrome Web Store rejects a package upload at the same version as what's
already live. Bump `version` in `extension/chrome/manifest.json` before
building — semver-ish: patch for fixes, minor for new capability (new
commands, new context-menu entries, etc).

## 2. Build + test

```bash
cd extension/chrome
npm install
npm run build   # tsc compiles src/*.ts -> src/*.js in place
npm test
```

## 3. Package

Only these files ship —

```
manifest.json
popup.html
options.html
icons/
src/*.js
```

```PowerShell

Compress-Archive -Path "C:\Users\leone\Desktop\codeKitchen\ownix\extension\chrome\dist\ownix-capture-0.2.0" -DestinationPath "C:\Users\leone\Desktop\codeKitchen\ownix\extension\chrome\dist\ownix-capture-0.2.0.zip"
```

`.ts` sources, `test/`, `node_modules`,
`package*.json`, `tsconfig.json`, and `vitest.config.ts` do not go in the
zip

Copy them into `dist/ownix-capture-<version>/` and zip that folder
(`dist/ownix-capture-<version>.zip`). `dist/` is gitignored — this is a
local build artifact, not something to commit.

## 4. Check whether this update needs re-review of permissions

Open the Web Store developer dashboard listing → **Privacy practices** tab
only needs revisiting if this update adds/changes `permissions` or
`host_permissions` in `manifest.json`. Adding entries under `commands`
(keyboard shortcuts) does **not** count — no extra review there.

## 5. Upload

1. [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole) → **Ownix Capture**.
2. **Package** tab → **Upload new package** → select the zip from step 3.
3. **Store listing** tab — only touch this if the description/screenshots
   changed; otherwise leave as-is.
4. **Submit for review**.

## 6. Wait for review

Review is a Google process, not instant — usually hours, occasionally
longer. Watch:

- The dashboard item status (Draft → In review → Published, or Rejected
  with a reason).
- The developer account's email for reviewer questions or a rejection
  notice.

## 7. Verify live

Once **Published**:

- `chrome://extensions` → the installed copy should offer/auto-apply the
  update (or reload it manually).
- Confirm the version shown matches what was bumped in step 1.
- Exercise the changed behavior end-to-end (e.g. the four capture
  shortcuts: `Ctrl+Shift+1`–`4`) against the paired dashboard account.

## Reviewer access (only needed if permissions/host access changed)

If a future update _does_ need reviewer testing (new scope, new host
permission), see the **Chrome Web Store reviewer access** section in
`extension/chrome/README.md` — temporary `REVIEWER_LOGIN_*` env vars that
let a Chrome reviewer sign in without Telegram. Not needed for a
same-permissions update like this one.
