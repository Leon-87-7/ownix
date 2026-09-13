"""Canonical DDL for every table this service owns.

The single source of truth for the schema: `init_db()` runs `SCHEMA_SQL` on a
fresh database, and `src/db/migrations/` carries an existing one forward to the
same shape. Nothing else may declare a table — a second `CREATE TABLE` for a
table named here is a second source of truth that has to be hand-synced.
"""

from __future__ import annotations


# Shared verbatim between SCHEMA_SQL (fresh installs, executescript at
# database.py's init_db()) and _migrate_newsletter_archive_polling (existing
# installs). A migration test asserts the two paths produce identical
# sqlite_master output (issue #609) — SQLite stores a CREATE statement's
# internal whitespace verbatim, so these must be the *same* string object in
# both places, not independently retyped copies that merely look alike.
_PUBLICATIONS_TABLE_SQL = """CREATE TABLE IF NOT EXISTS publications (
    id                       TEXT PRIMARY KEY,
    archive_url              TEXT NOT NULL UNIQUE,
    feed_url                 TEXT,
    issue_path_prefix        TEXT,
    fetched_title            TEXT,
    last_resolved_at         TIMESTAMP,
    last_successful_poll_at  TIMESTAMP,
    next_poll_after          TIMESTAMP,
    poll_lease_until         TIMESTAMP,
    poll_failures            INTEGER NOT NULL DEFAULT 0,
    created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"""

_PUBLICATION_ISSUES_TABLE_SQL = """CREATE TABLE IF NOT EXISTS publication_issues (
    publication_id TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
    slug           TEXT NOT NULL,
    url            TEXT NOT NULL,
    title          TEXT,
    published_at   TEXT,
    source_order   INTEGER NOT NULL,
    first_seen_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    body_html      TEXT,
    body_fetched_at TIMESTAMP,
    skip_reason    TEXT,
    PRIMARY KEY (publication_id, slug)
)"""

_NEWSLETTER_WATCHES_TABLE_SQL = """CREATE TABLE IF NOT EXISTS newsletter_watches (
    id             TEXT PRIMARY KEY,
    chat_id        INTEGER NOT NULL,
    publication_id TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
    space_id       TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    watched_from   TIMESTAMP NOT NULL,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, publication_id)
)"""

_NEWSLETTER_WATCHES_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_newsletter_watches_publication_id\n"
    "    ON newsletter_watches(publication_id)"
)

_EMAIL_DIGEST_PAYLOADS_TABLE_SQL = """CREATE TABLE IF NOT EXISTS email_digest_payloads (
    job_id         TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    watch_id       TEXT REFERENCES newsletter_watches(id) ON DELETE SET NULL,
    publication_id TEXT NOT NULL,
    slug           TEXT NOT NULL,
    context_md     TEXT,
    UNIQUE(watch_id, slug),
    FOREIGN KEY (publication_id, slug)
        REFERENCES publication_issues(publication_id, slug) ON DELETE RESTRICT
)"""

_EMAIL_DIGEST_PAYLOADS_WATCH_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_email_digest_payloads_watch_id\n"
    "    ON email_digest_payloads(watch_id)"
)

_EMAIL_DIGEST_PAYLOADS_SLUG_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_email_digest_payloads_publication_slug\n"
    "    ON email_digest_payloads(publication_id, slug)"
)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS allowed_domains (
    chat_id     INTEGER NOT NULL,
    domain      TEXT NOT NULL,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, domain)
);

CREATE TABLE IF NOT EXISTS jobs (
    id                          TEXT PRIMARY KEY,         -- YYYYMMDD_HHMMSS_XXXX
    chat_id                     INTEGER NOT NULL,
    message_id                  INTEGER,
    url                         TEXT NOT NULL,
    source_url                  TEXT,
    content_type                TEXT NOT NULL,
    status                      TEXT NOT NULL DEFAULT 'pending',
    attempt                     INTEGER NOT NULL DEFAULT 1,
    error_msg                   TEXT,
    drive_url                   TEXT,
    title                       TEXT,
    original_title              TEXT,
    transcript                  TEXT,
    ai_category                 TEXT,
    ai_topic                    TEXT,
    ai_objective                TEXT,
    ai_action_points            TEXT,
    ai_tools                    TEXT,
    ai_market_data              TEXT,
    -- Mini-PRD auto slot (slice #6)
    prd_auto_status             TEXT,
    prd_auto_drive_file_id      TEXT,
    prd_auto_drive_url          TEXT,
    prd_auto_json               TEXT,
    -- Mini-PRD intent slot (slice #7)
    prd_intent_status           TEXT,
    prd_intent_drive_file_id    TEXT,
    prd_intent_drive_url        TEXT,
    prd_intent_json             TEXT,
    prd_intent_text             TEXT,
    prd_intent_completed_at     TEXT,
    sheets_row_id               TEXT,
    -- Template system (issue #17/#18)
    template                    TEXT,
    template_analysis           TEXT,
    key_phrases                 TEXT,
    validation_warning_sent     INTEGER DEFAULT 0,
    template_detection_method   TEXT,
    processing_time_ms          INTEGER,
    promise_gap                 TEXT,
    bot_message_id              INTEGER,
    -- Freestyle Gemini prompt (issue #51 / ADR-0012)
    freestyle_prompt            TEXT,
    best_frame_index            INTEGER,
    platform                    TEXT,
    video_id                    TEXT,
    og_image_url                TEXT,
    summary                     TEXT,
    links                       TEXT,
    telegram_delivery           TEXT NOT NULL DEFAULT 'on',
    code                        TEXT,
    code_lang                   TEXT,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at                TIMESTAMP,
    checklists_md               TEXT,
    checklists_generated_at     TEXT,
    -- Long-video screenshot capture (#580/#583)
    screenshots_status          TEXT,
    screenshots_drive_url       TEXT,
    screenshots_drive_folder_id TEXT,
    screenshots_generated_at    TIMESTAMP,
    video_duration_seconds      REAL,
    -- Symmetric transcript/enrichment Drive tracking (ADR-0057): drive_url is
    -- always the enrichment doc, transcript_drive_url is always the transcript doc.
    transcript_drive_url        TEXT,
    -- Resolved job->link key, persisted so tag filtering has a column to JOIN
    -- on (tags live on links). Written by the jobs read path, not at creation:
    -- the match runs through normalize_url(), which SQL can't call.
    link_id                     TEXT,
    CHECK(content_type IN ('short', 'long', 'unsized', 'article', 'repo', 'document', 'link')),
    CHECK(status IN ('held','pending','processing','transcript_done','enriching','done','error','cancelled')),
    CHECK(prd_auto_status IS NULL OR prd_auto_status IN ('generating','done','error')),
    CHECK(prd_intent_status IS NULL OR prd_intent_status IN ('generating','done','error')),
    CHECK(telegram_delivery IN ('off','on'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_chat_id ON jobs(chat_id);
CREATE INDEX IF NOT EXISTS idx_jobs_chat_created ON jobs(chat_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url);

CREATE TABLE IF NOT EXISTS job_thumbnails (
    job_id     TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    bytes      BLOB NOT NULL,
    mime       TEXT NOT NULL,
    width      INTEGER,
    height     INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User-managed per-chat domain ignore list for Gemini Vision link filtering (/ignore command).
CREATE TABLE IF NOT EXISTS ignored_domains (
    chat_id     INTEGER NOT NULL,
    domain      TEXT NOT NULL,
    added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, domain)
);

-- Per-chat conversational mode (slice #7 uses this for ✍️ Text your intent flow).
-- Schema created here in slice #1; behaviour wired in slice #7.
CREATE TABLE IF NOT EXISTS chat_state (
    chat_id      INTEGER PRIMARY KEY,
    mode         TEXT NOT NULL,
    job_id       TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    CHECK(mode IN ('awaiting_intent', 'awaiting_freestyle', 'awaiting_email'))
);

-- Jina Reader markdown cache (issue #60 / ADR-0013).
CREATE TABLE IF NOT EXISTS markdown_cache (
    url         TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    fetched_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Web dashboard users (issue #84 / S1 auth spine).
CREATE TABLE IF NOT EXISTS users (
    tg_id       INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT NOT NULL,
    last_name   TEXT,
    photo_url   TEXT,
    email       TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK(status IN ('pending','approved','blocked','deleting'))
);

-- idx_users_email_nocase is NOT created here (unlike CREATE TABLE IF NOT
-- EXISTS, a bare CREATE INDEX runs unconditionally every init_db() call,
-- including against an old non-fresh DB whose users table doesn't have
-- `email` yet — that migration hasn't run at this point in the fresh-vs-
-- migrate branch below). It's created once, unconditionally, right after
-- _run_migrations() — same reason idx_jobs_source_url sits there instead of
-- in this script (see the comment at that call site).

CREATE TABLE IF NOT EXISTS identity_links (
    provider   TEXT NOT NULL,
    subject    TEXT NOT NULL,
    owner_id   INTEGER NOT NULL REFERENCES users(tg_id) ON DELETE CASCADE,
    verified   INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(provider, subject)
);

CREATE TABLE IF NOT EXISTS user_settings (
    chat_id    INTEGER NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, key)
);

CREATE TABLE IF NOT EXISTS google_oauth_tokens (
    chat_id             INTEGER PRIMARY KEY,
    encrypted_token     TEXT NOT NULL,
    scopes              TEXT NOT NULL DEFAULT '',
    revoked_notified_at TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS google_oauth_states (
    state      TEXT PRIMARY KEY,
    chat_id    INTEGER NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Second Brain semantic link graph (src/brain.py data-access layer).
CREATE TABLE IF NOT EXISTS links (
    id            TEXT PRIMARY KEY,
    chat_id       INTEGER,
    url           TEXT NOT NULL,
    title         TEXT,
    topic         TEXT,
    description   TEXT,
    source_job    TEXT NOT NULL,
    embedding     BLOB,
    drive_file_id TEXT,
    seen_count    INTEGER NOT NULL DEFAULT 1,
    last_seen_at  TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    stars         INTEGER,
    pushed_at     TEXT,
    archived      INTEGER NOT NULL DEFAULT 0,
    og_image_url  TEXT
);
CREATE INDEX IF NOT EXISTS idx_links_url ON links(url);
CREATE UNIQUE INDEX IF NOT EXISTS idx_links_chat_url_unique ON links(chat_id, url);
CREATE INDEX IF NOT EXISTS idx_links_updated_at ON links(updated_at);

-- Tag vocabulary for job tagging (issue #87 / S4).
CREATE TABLE IF NOT EXISTS tags (
    id         TEXT PRIMARY KEY,
    chat_id    INTEGER NOT NULL,
    name       TEXT NOT NULL,
    meaning    TEXT NOT NULL DEFAULT '',
    color      TEXT NOT NULL DEFAULT '#8b5cf6',
    icon       TEXT,
    pinned     INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, name)
);

-- User-defined enrichment templates (issue #90).
CREATE TABLE IF NOT EXISTS templates (
    id                  TEXT PRIMARY KEY,
    chat_id             INTEGER NOT NULL DEFAULT 0,
    name                TEXT NOT NULL,
    description         TEXT NOT NULL DEFAULT '',
    extra_instructions  TEXT NOT NULL DEFAULT '',
    trigger_patterns    TEXT NOT NULL DEFAULT '',
    brave_search        INTEGER NOT NULL DEFAULT 0,
    content_type_scope  TEXT NOT NULL DEFAULT '',
    is_builtin          INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, name)
);

-- Job notes (issue #88 / S5).
CREATE TABLE IF NOT EXISTS job_annotations (
    job_id     TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    notes      TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Link-tag links (issue #382).
CREATE TABLE IF NOT EXISTS link_tags (
    link_id TEXT NOT NULL REFERENCES links(id) ON DELETE CASCADE,
    tag_id  TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (link_id, tag_id)
);

-- Job-tag links (issue #88 / S5).
CREATE TABLE IF NOT EXISTS job_tags (
    job_id  TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    tag_id  TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, tag_id)
);

-- Named collections of jobs (issue #89 / S6).
CREATE TABLE IF NOT EXISTS spaces (
    id         TEXT PRIMARY KEY,
    chat_id    INTEGER NOT NULL,
    name       TEXT NOT NULL,
    color      TEXT NOT NULL DEFAULT '#6366f1',
    icon       TEXT NOT NULL DEFAULT 'folder',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, name)
);
CREATE INDEX IF NOT EXISTS idx_spaces_chat_id ON spaces(chat_id);

-- Jobs pinned into a space (issue #89 / S6).
CREATE TABLE IF NOT EXISTS space_urls (
    space_id   TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    job_id     TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    added_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (space_id, job_id)
);

-- Per-space editorial context documents (issue #93 / S7).
-- source_url: the newsletter issue (or other origin) a blob was generated
-- from, so the UI can link back to it. NULL for manually-authored blobs.
CREATE TABLE IF NOT EXISTS context_blobs (
    id         TEXT PRIMARY KEY,
    space_id   TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    content    TEXT NOT NULL DEFAULT '',
    source_url TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_context_blobs_space_id ON context_blobs(space_id);

-- Watched newsletter publications — shared across tenants, no chat_id: a
-- public archive is byte-identical for every viewer (ADR-0060, PLAN.md §1).
-- fetched_title is scraped metadata, never user-facing.
{publications_table_sql};

-- Shared seen-set of published issues, and the single copy of each fetched
-- issue body (never duplicated per watcher). skip_reason marks an issue
-- terminally skipped (e.g. 'oversize') so it stops being selected as work.
{publication_issues_table_sql};

-- Per-tenant watch on a publication. watched_from is a TIMESTAMP (issue
-- watermark), not a slug — slugs are publisher strings with no chronological
-- order (PLAN.md §1).
{newsletter_watches_table_sql};
{newsletter_watches_index_sql};

-- Lightweight links extracted from a digest. Only explicit promotion creates jobs.
CREATE TABLE IF NOT EXISTS digest_candidates (
    id            TEXT PRIMARY KEY,
    space_id      TEXT NOT NULL REFERENCES spaces(id) ON DELETE CASCADE,
    url           TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    title         TEXT,
    thumbnail_url TEXT,
    status        TEXT NOT NULL DEFAULT 'pending',
    job_id        TEXT REFERENCES jobs(id) ON DELETE SET NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK(status IN ('pending','promoting','promoted','dismissed')),
    UNIQUE(space_id, canonical_url)
);
CREATE INDEX IF NOT EXISTS idx_digest_candidates_space_status
    ON digest_candidates(space_id, status, created_at);

-- Per-watcher digest job payload. The issue body itself lives once in
-- publication_issues.body_html; this row only points at it via the composite
-- FK below, plus the per-issue Gemini context (generated once by the poll
-- worker, never per-job). Cleared (context_md -> NULL) on success, retained
-- on error rows so a retry needs no regeneration.
-- The two indexes below are deliberately NOT spliced in here (see the
-- idx_jobs_source_url comment further down): on an existing database this
-- table already exists in its pre-#609 shape (no watch_id column), so
-- CREATE TABLE IF NOT EXISTS no-ops and an index on watch_id would crash
-- startup with "no such column" before the migration that rebuilds this
-- table with the new shape has run.
{email_digest_payloads_table_sql};

CREATE TABLE IF NOT EXISTS document_outputs (
    id          TEXT PRIMARY KEY,
    job_id      TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    gcs_key     TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK(kind IN ('raw_txt','raw_md','summary','clean','freestyle'))
);
CREATE INDEX IF NOT EXISTS idx_document_outputs_job_id ON document_outputs(job_id, created_at);
-- Singular kinds (raw_txt/raw_md/summary/clean) are one-per-job and upserted;
-- freestyle accumulates as history, so it's excluded from the uniqueness rule.
CREATE UNIQUE INDEX IF NOT EXISTS idx_document_outputs_singular ON document_outputs(job_id, kind) WHERE kind <> 'freestyle';

-- Transactional outbox for durable Job purge enqueuing.
CREATE TABLE IF NOT EXISTS purge_tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT NOT NULL,
    chat_id         INTEGER NOT NULL,
    task_payload    TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    enqueued_at     TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_purge_tasks_enqueued ON purge_tasks(enqueued_at);

-- Append-only audit log of admin / security-relevant actions: who did what, to
-- which entity, when. INTEGER PK like purge_tasks — rows are inserted, never
-- updated. chat_id is the acting user (NULL for system-initiated actions);
-- metadata holds an optional JSON blob of extra context.
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id     INTEGER,
    action      TEXT NOT NULL,
    target_type TEXT,
    target_id   TEXT,
    metadata    TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_chat ON audit_log(chat_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_target ON audit_log(target_type, target_id);

-- Enforce the append-only contract in the engine, not just by convention: a
-- written audit row can never be altered or removed.
CREATE TRIGGER IF NOT EXISTS audit_log_no_update
BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only');
END;
CREATE TRIGGER IF NOT EXISTS audit_log_no_delete
BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'audit_log is append-only');
END;
""".format(
    publications_table_sql=_PUBLICATIONS_TABLE_SQL,
    publication_issues_table_sql=_PUBLICATION_ISSUES_TABLE_SQL,
    newsletter_watches_table_sql=_NEWSLETTER_WATCHES_TABLE_SQL,
    newsletter_watches_index_sql=_NEWSLETTER_WATCHES_INDEX_SQL,
    email_digest_payloads_table_sql=_EMAIL_DIGEST_PAYLOADS_TABLE_SQL,
)
