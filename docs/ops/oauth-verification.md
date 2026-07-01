# Google OAuth consent screen — production publishing + verification

Tracks issue #203 (parent #201, pinned by ADR-0030). HITL + external — the
verification itself is a Google review (days–weeks), no code changes.

## Scopes

Only two, deliberately no restricted scope (would trigger a paid CASA assessment):

| Scope | API | Sensitivity |
| --- | --- | --- |
| `.../auth/drive.file` | Google Drive API | non-sensitive |
| `.../auth/spreadsheets` | Google Sheets API | sensitive (approval required) |

Never add `drive` or `drive.readonly` — full/read Drive access is restricted.

## Consent screen fields (as configured)

- App name: `VIG`
- User support email: `leoneidelman09@gmail.com`
- Developer contact email: `leoneidelman09@gmail.com`
- App logo: `vig_logo_primary_space_bg.jpg` (uploading a logo forces
  verification even without a sensitive scope — moot here since `spreadsheets`
  already requires it)
- Homepage: `https://app.leondev.xyz`
- Privacy policy: `https://app.leondev.xyz/privacy`
- Terms of service: `https://app.leondev.xyz/terms`
- Authorized domain: `leondev.xyz`

## Sensitive scope justification (`spreadsheets`)

Pasted into "How will the scopes be used?" on the Data Access tab:

> VIG is a Telegram bot that lets a user send video links (Reels/Shorts/TikTok/YouTube);
> the app runs AI enrichment on them and saves the results into a spreadsheet in the
> user's own Google account. On first connect, VIG creates one spreadsheet ("vig"
> tracker) via the Sheets API and appends a row per processed video (title, tags,
> summary, links). The `spreadsheets` scope is required because Sheets has no narrower
> "app-created-file-only" scope equivalent to Drive's `drive.file` — write access to a
> spreadsheet requires the full scope even though VIG only ever touches the single file
> it created. VIG never reads, lists, or modifies any other spreadsheet in the user's
> account. Users can revoke access anytime via `/disconnect` in the bot or Google
> Account settings.

## Publishing checklist

- [x] DNS TXT domain ownership verified (leave the record in place — removing it
      drops verification).
- [x] Privacy/terms pages deployed live at `app.leondev.xyz/privacy` and `/terms`.
- [x] Consent screen app info + branding filled in.
- [x] Scopes added: `drive.file` (non-sensitive) + `spreadsheets` (sensitive).
- [x] Scope justification submitted.
- [x] Publishing status → **In production** (External, 1/100 user cap used).
- [x] Web OAuth client created ("Web client 1"): JS origin `https://app.leondev.xyz`,
      redirect URI `https://app.leondev.xyz/api/auth/google/callback`. Credentials
      stored as `GOOGLE_OAUTH_WEB_CLIENT_ID`/`GOOGLE_OAUTH_WEB_CLIENT_SECRET` in
      `.env` (placeholders only in `.env.example`). Distinct from the legacy
      `GOOGLE_OAUTH_CLIENT_ID`/`SECRET`/`REFRESH_TOKEN` (Desktop-app type, backs
      the single-operator export path — unrelated, left alone). Mini App (`#205`)
      needs no separate client — converges on this same callback per ADR-0030.
- [ ] `#204` (per-user "Connect Google," web) built — implements the
      `/api/auth/google/callback` route this client now points at. No `/connect`
      command exists in `src/` yet; this is the actual blocker below.
- [ ] `/connect` flow verified working end-to-end (blocks the demo video —
      can't record a real consent → Drive/Sheets write → revoke cycle on a
      flow that doesn't exist yet). Building/testing this does **not** need to
      wait on Google's review — an unverified in-production app still works for
      up to 100 test users behind a click-through warning.
- [ ] Demo video recorded once the flow is confirmed working.
- [ ] Verification submitted (justification + demo video) via **Go to
      verification center**.
- [ ] Verification approved — unverified-app warning gone. **`#203` closes here.**

## Demo video script (for verification submission)

Google wants a short screen recording proving the consent flow matches the
justification — what the user sees, and that the app only touches what it says.

1. **Start on the bot**, not the console. Show a fresh Telegram chat with VIG,
   send `/connect` (or the equivalent command that starts the OAuth flow).
2. **Consent screen** — let the Google OAuth prompt render fully, don't cut
   past it. Narrate/caption: "User is shown the two scopes VIG requests:
   Drive (files created by this app only) and Sheets."
3. **Approve** the consent.
4. **Immediate effect** — switch to the user's actual Google Drive, show the
   new `/vig` folder and spreadsheet just created. This proves `drive.file`
   scope is used only for app-created files.
5. **Send one video link** to the bot, wait for processing, then show the new
   row appended in the Sheet. This proves the `spreadsheets` scope usage
   matches the justification text.
6. **Revoke** — send `/disconnect`, then show `myaccount.google.com/permissions`
   with the VIG grant gone, proving revocation works.
7. Keep it under ~3–5 minutes, no narration required if captions/on-screen
   text carry the explanation — Google's reviewers read more than they listen.

Upload to an unlisted YouTube link (Google's submission form asks for a URL,
not a file upload) and paste that link into the verification request.

## After submission

Google may email the developer contact address with follow-up questions or a
request to adjust scope wording/branding — check that inbox, don't just wait
silently. Once approved, the "Google hasn't verified this app" warning
disappears from the consent screen for all users.
