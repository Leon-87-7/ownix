# Ownix Email Digest Worker

Cloudflare Email Routing Worker for newsletter digest ingestion. It parses the
incoming MIME message with `postal-mime`, keeps Cloudflare's envelope recipient
as `envelopeTo`, and forwards JSON to `/webhook/email-digest` with the shared
secret header.

Manual deploy checklist:

1. Install dependencies in this folder: `npm install`.
2. Log in to Cloudflare: `npx wrangler login`.
3. Set the shared secret binding:
   `npx wrangler secret put OWNIX_EMAIL_SECRET`.
4. Confirm `OWNIX_EMAIL_WEBHOOK_URL` in `wrangler.toml` points at the API.
5. Deploy the Worker with Wrangler.
6. In Cloudflare Email Routing for `leondev.xyz`, create a catch-all custom
   address rule that routes to this Worker.

Do not store `OWNIX_EMAIL_SECRET` in `wrangler.toml` or source control. The
Python API must use the same value in `EMAIL_WEBHOOK_SECRET`.
