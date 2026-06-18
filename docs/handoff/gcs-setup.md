# GCS setup (human steps) — document pipeline storage

The document pipeline stores PDFs + parsed text in a Google Cloud Storage
bucket. The code compiles and **all unit tests run without any of this** (the
GCS client is mocked). You only need these steps before a real PDF gets
processed end-to-end.

## Service account ≠ company account

Service accounts are **not** Workspace/company-only. Any GCP project — including
one created with a plain personal Gmail — can create them for free. The
"service account → Shared Drives / Workspace" note in `src/services/google_auth.py`
is about **Drive Shared Drives**, which is a Drive-specific thing. GCS buckets
live in a GCP *project*, not in Drive, so a personal account works fine.

A service account is the recommended identity for GCS here because it gets its
scope at request time — sidestepping the OAuth refresh-token scope trap below.

## Steps (personal Gmail is fine)

1. https://console.cloud.google.com → create a project (free).
2. Enable the **Cloud Storage API**, then create a **bucket**.
   Its name goes in env var `GOOGLE_STORAGE_BUCKET`.
3. IAM & Admin → **Service Accounts** → create one → create a **JSON key**, download it.
4. Grant that service account **Storage Object Admin** on the bucket
   (Bucket → Permissions → Grant access).
5. Point `GOOGLE_SERVICE_ACCOUNT_JSON` at the downloaded key file.

That's it. `storage.py` builds its client from whichever credential is present:
service account if `GOOGLE_SERVICE_ACCOUNT_JSON` is set, OAuth refresh token
otherwise.

## The OAuth refresh-token trap (why we prefer the SA)

An OAuth refresh token only carries the scopes consented to **when it was
minted**. If your existing refresh token was granted only Drive/Sheets scopes,
adding `devstorage.read_write` to the `Credentials` object at refresh time does
**not** grant it — you cannot broaden an existing refresh token. You'd have to
re-consent to mint a new one including the storage scope. A service account has
no such limitation.
