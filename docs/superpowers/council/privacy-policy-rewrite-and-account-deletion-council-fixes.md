# Privacy Policy Rewrite & Account Deletion — Council Review Fixes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Reviewed commit:** `870f86d`
**Diff range:** `main..HEAD` (branch: `privacy-policy-rewrite-and-account-deletion`)

**Goal:** Fix every finding from the `/council-review` of this branch (5 parallel reviewers — ponytail/over-engineering, correctness/security, interfaces/UX, react-component, python-backend — synthesized: 0 Blocker, 5 Major, 8 Minor, 2 Nit). The PR adds self-serve "delete my account" (`DELETE /api/auth/me`, `src/services/account.py`, a `"deleting"` user-status exclusivity lock, resume-on-login logic, a DB migration widening a `CHECK` constraint, a Controls-page "Danger zone" UI) plus a Privacy Policy/Terms rewrite. The Majors are: a third session-minting login path (`/api/auth/handoff`) missing the `"deleting"` guard the other two login paths already have; no mutual exclusion between two concurrent `DELETE /api/auth/me` calls; a non-atomic table-rebuild migration that can destroy every user row on a crash; a destructive-button-before-consequences DOM order bug on narrow viewports; and a hand-rolled fetch that swallows the server's real error message where an existing helper already does this correctly.

**Architecture:** No new subsystems. Every task is a scoped fix inside the existing FastAPI/SQLite/Redis backend (`src/`) or the Next.js dashboard (`web/`), touching only the files the PR itself touched. Tasks are ordered by reviewer-assigned priority (security/concurrency Majors first, then the migration atomicity fix, then the UI Majors, then Minors in finding order, then Nits) and are independently committable.

**Tech Stack:** Python 3.11 (FastAPI, aiosqlite, structlog), pytest + pytest-asyncio; Next.js 14 App Router, React, TypeScript, Tailwind, Vitest + Testing Library, Radix UI.

**Spec:** No separate spec document — the 15 synthesized council findings (reproduced per-task below, each independently confirmed by at least one of the five reviewers) are the spec for this plan.

## Global Constraints

- Run Python tests via the **PowerShell tool**, never Bash — the rtk hook only intercepts the Bash tool and mangles/hangs pytest regardless of phrasing. Use the exact scoped command given in each task's verification step, not a bare "run the tests."
- Run frontend tests with `npm test` / `npm run test:run` (Vitest) from `web/`, and `npm run lint` for lint-affecting tasks — do not invent a different runner.
- Reuse existing helpers instead of reinventing them: `apiDelete` (`web/lib/fetch-utils.ts:177`), `ConfirmDialog` (`web/components/ui/confirm-dialog.tsx`), `database._execute_rowcount` / `database.connection()` (`src/database.py`). Do not create a new component or a new fetch wrapper where one already exists.
- Keep diffs minimal per finding — do not use a finding as an excuse to refactor adjacent code the finding didn't call out.
- Do not scope-creep into the two explicitly-out-of-scope areas: (a) fixing the same unwrapped-migration-rebuild pattern in `_migrate_v22_v23`'s `jobs` rebuild or `_migrate_v23_v24`'s `chat_state_v24` rebuild (pre-existing convention, separate future migration-safety pass — Task 3 touches `_migrate_v43_v44` only); (b) moving per-job cleanup to the worker/queue (Task 12's fix is a documenting comment, not a redesign).
- Each task ends in its own commit with a conventional-commit message (`fix:`, `refactor:`, `perf:`, `docs:`) — do not batch unrelated tasks into one commit.
- Design-system edits (colors, text treatments) must follow `DESIGN.md` at the repo root — reuse existing Tailwind tokens (`text-status-error`, etc.); do not invent new ones. `DESIGN.md` forbids colored side-stripe accents but not text-color cues (`"Don't use side-stripe borders as colored accents. Use full borders, labeled badges, or background tints instead."` — a text-only treatment is none of those, so it's allowed).
- Run the scoped backend test command after every backend-touching task and the scoped frontend test command after every frontend-touching task — not just once at the end of the plan.
- Do not merge to `main`/`master` unless the user explicitly names it as the target in that message (`.claude/rules/no-merge-to-main.md`).

---

## Task 1: `/api/auth/handoff` is missing the "deleting" status guard (Major #1)

**Files:**
- Modify: `src/api/auth.py:250-284` (`redeem_handoff_login`)
- Test: `tests/test_auth.py` (add to `class TestAccountDeletionLock`)

**Finding:** `redeem_handoff_login` (`POST /api/auth/handoff`) is the third session-minting login path. `_login_telegram_user` (lines 59-67) and `miniapp_session` (lines 120-125) both already check `get_user_status(...) == "deleting"` and refuse to mint a session — but `redeem_handoff_login` mints one unconditionally once a handoff token redeems to a `chat_id` and `database.get_user(chat_id)` returns non-`None`. A 5-minute dashboard-notification handoff token can therefore mint a live session into an account whose row is mid-deletion.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_auth.py` inside `class TestAccountDeletionLock` (this class already imports `asyncio`, `json`, `FakeRedis`, `TOKEN`, and has the `auth_client` fixture — follow the existing tests in this class for style, e.g. `test_login_resumes_stuck_deletion_instead_of_minting_session` just above it):

```python
    def test_handoff_login_resumes_stuck_deletion_instead_of_minting_session(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The dashboard-notification handoff login is a third session-minting
        path (alongside _login_telegram_user and miniapp_session) — it must
        not mint a session into an account whose row is mid-deletion."""
        import src.auth.session as session_module
        from src import database

        asyncio.run(
            database.upsert_user(
                tg_id=555009, username="handoff_user", first_name="H", last_name=None, photo_url=None
            )
        )
        asyncio.run(database.set_user_status(555009, "deleting"))

        token = asyncio.run(session_module.mint_dashboard_handoff(555009, ttl=3600))

        resp = auth_client.post(
            "/api/auth/handoff",
            data={"token": token, "job_id": "job_abc"},
            follow_redirects=False,
        )

        assert resp.status_code == 401
        assert "vig_session=" not in resp.headers.get("set-cookie", "")
        assert asyncio.run(database.get_user(555009)) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run (PowerShell): `python -m pytest tests/test_auth.py::TestAccountDeletionLock::test_handoff_login_resumes_stuck_deletion_instead_of_minting_session -v --timeout=60`
Expected: FAIL — today the route mints a session and redirects with 303 instead of rejecting with 401.

- [ ] **Step 3: Add the guard**

In `src/api/auth.py`, change `redeem_handoff_login`:

```python
@auth_router.post("/handoff")
async def redeem_handoff_login(
    token: str = Form(..., max_length=512), job_id: str = Form(...)
) -> RedirectResponse:
    """Redeem a job-link handoff token and land the user straight on their job page."""
    if not _JOB_ID_RE.fullmatch(job_id):
        raise HTTPException(status_code=400, detail="Invalid job_id")

    chat_id = await session_store.redeem_dashboard_handoff(token)
    if chat_id is None:
        raise HTTPException(status_code=401, detail="This link has expired or was already used")

    # See _login_telegram_user: resume a deletion left mid-flight rather than
    # minting a session into a half-deleted account. Unlike the other two
    # login paths, this route redirects rather than returning a session JSON
    # body, so on resume it rejects with the same 401 the "user is None" path
    # below already uses (delete_account() will have just made that true).
    if await database.get_user_status(chat_id) == "deleting":
        await delete_account(chat_id)
        log.info("auth.resumed_account_deletion", tg_id=chat_id)
        raise HTTPException(status_code=401, detail="Dashboard access is unavailable")

    user = await database.get_user(chat_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Dashboard access is unavailable")
```

(The rest of the function — minting the session and building the redirect — is unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run (PowerShell): `python -m pytest tests/test_auth.py::TestAccountDeletionLock::test_handoff_login_resumes_stuck_deletion_instead_of_minting_session -v --timeout=60`
Expected: PASS.

- [ ] **Step 5: Run the scoped suite for regressions**

Run (PowerShell): `python -m pytest tests/test_auth.py tests/test_account.py tests/test_database.py -q --timeout=60`
Expected: all pass (compare failure count against the pre-existing baseline noted in project memory if any unrelated failures appear — do not attribute pre-existing failures to this change).

- [ ] **Step 6: Commit**

```bash
git add src/api/auth.py tests/test_auth.py
git commit -m "fix(auth): reject dashboard handoff login into a mid-deletion account"
```

---

## Task 2: No mutual exclusion between concurrent `DELETE /api/auth/me` calls (Major #2)

**Files:**
- Modify: `src/database.py` (add `begin_account_deletion`, near `set_user_status` at line ~2233)
- Modify: `src/api/auth.py:342-374` (`delete_account_route`)
- Test: `tests/test_database.py`, `tests/test_auth.py` (add to `class TestAccountDeletionLock`)

**Finding:** `delete_account_route` calls `await database.set_user_status(tg_id, "deleting")` unconditionally — no rowcount/compare-and-set check. `DELETE /api/auth/me` is in `_PRE_APPROVAL_AUTH_PATHS` (`src/auth/middleware.py:35-40`), so it stays reachable even once status is `"deleting"`. Two concurrent calls (a second device/tab with a still-valid session, or a login-resume race) both flip status to `"deleting"` harmlessly, then both run `delete_account()` in parallel. `delete_job()` inserts a `purge_tasks` row unconditionally whenever `purge_payload` is truthy, regardless of whether the `DELETE` actually removed a row — so two concurrent runs produce duplicate `purge_tasks` rows and double Google-token-revoke calls.

**Interfaces:**
- Produces: `database.begin_account_deletion(tg_id: int) -> bool` — atomically flips `status` to `"deleting"` unless it is already `"deleting"`; returns `True` if this call won the lock, `False` if another call already holds it.

- [ ] **Step 1: Write the failing test (DB-level)**

Add to `tests/test_database.py` (follow the style of the other `@pytest.mark.asyncio` tests using `tmp_path`/`monkeypatch` in this file, e.g. `test_migration_creates_audit_log_and_triggers_directly`):

```python
@pytest.mark.asyncio
async def test_begin_account_deletion_is_exclusive(tmp_path, monkeypatch) -> None:
    """Only the first caller wins the lock; a second call on an already-
    'deleting' row must report False instead of re-flipping the status
    (finding #2: two concurrent DELETE /api/auth/me calls must not both
    run delete_account())."""
    from src import database

    db_file = str(tmp_path / "lock_test.db")
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    monkeypatch.setattr("src.database.settings.DB_PATH", db_file)
    await database.init_db()
    await database.upsert_user(tg_id=1, username="u", first_name="U", last_name=None, photo_url=None)
    await database.set_user_status(1, "approved")

    first = await database.begin_account_deletion(1)
    second = await database.begin_account_deletion(1)

    assert first is True
    assert second is False
    assert await database.get_user_status(1) == "deleting"
```

- [ ] **Step 2: Run test to verify it fails**

Run (PowerShell): `python -m pytest tests/test_database.py::test_begin_account_deletion_is_exclusive -v --timeout=60`
Expected: FAIL with `AttributeError: module 'src.database' has no attribute 'begin_account_deletion'`.

- [ ] **Step 3: Add `begin_account_deletion` to `src/database.py`**

Insert immediately after `set_user_status` (after the block ending at line 2232, before `set_user_email`):

```python
async def begin_account_deletion(tg_id: int) -> bool:
    """Atomically flip status to "deleting" unless a deletion is already in
    progress. Returns True if this call acquired the lock, False if another
    concurrent call (a second device/tab, or a login-resume race) already
    holds it — the caller should treat False as "nothing left to do here"
    rather than running delete_account() a second time.
    """
    rowcount = await _execute_rowcount(
        "UPDATE users SET status = 'deleting', updated_at = CURRENT_TIMESTAMP "
        "WHERE tg_id = ? AND status != 'deleting'",
        (tg_id,),
    )
    log.info("account_deletion_lock_attempted", tg_id=tg_id, acquired=rowcount > 0)
    return rowcount > 0
```

- [ ] **Step 4: Run test to verify it passes**

Run (PowerShell): `python -m pytest tests/test_database.py::test_begin_account_deletion_is_exclusive -v --timeout=60`
Expected: PASS.

- [ ] **Step 5: Write the failing test (route-level)**

Add to `tests/test_auth.py` inside `class TestAccountDeletionLock`:

```python
    def test_delete_account_route_short_circuits_when_already_deleting(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A second concurrent DELETE /api/auth/me (another tab/device with a
        still-valid session, since /api/auth/me stays reachable during
        deletion) must not run delete_account() a second time."""
        import src.auth.session as session_module
        from src import database
        from src.api import auth as auth_api

        asyncio.run(
            database.upsert_user(
                tg_id=555008, username="race_user", first_name="R", last_name=None, photo_url=None
            )
        )
        # Simulate the first concurrent call having already acquired the lock.
        asyncio.run(database.set_user_status(555008, "deleting"))
        user = {"id": 555008, "username": "race_user"}
        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:race-sid"] = json.dumps(user)

        called = False

        async def spy_delete_account(chat_id: int) -> None:
            nonlocal called
            called = True

        monkeypatch.setattr(auth_api, "delete_account", spy_delete_account)

        resp = auth_client.delete("/api/auth/me", cookies={"vig_session": "race-sid"})

        assert resp.status_code == 204
        assert called is False
```

- [ ] **Step 6: Run test to verify it fails**

Run (PowerShell): `python -m pytest tests/test_auth.py::TestAccountDeletionLock::test_delete_account_route_short_circuits_when_already_deleting -v --timeout=60`
Expected: FAIL — `delete_account` is currently called unconditionally, so `called` is `True`.

- [ ] **Step 7: Use the lock in `delete_account_route`**

In `src/api/auth.py`, change `delete_account_route`:

```python
@auth_router.delete("/me", status_code=204)
async def delete_account_route(request: Request) -> Response:
    """Self-serve full account deletion: hard-deletes every job/link/credential/
    setting owned by the caller, disconnects Google, then ends the session.

    begin_account_deletion() atomically flips status to "deleting" (and the
    session is revoked) *before* the cleanup runs, not after: every other
    account-write route already rejects non-"approved" users
    (src/auth/middleware.py), so flipping status first shuts out concurrent
    writes from other sessions/devices, and revoking this session first
    closes the same-tab race the naive "delete then revoke" order leaves
    open. The lock is compare-and-set (WHERE status != 'deleting'), so a
    second concurrent call — another tab/device with a still-valid session,
    since /api/auth/me stays reachable during deletion — short-circuits here
    instead of running delete_account() a second time (which would otherwise
    insert duplicate purge_tasks rows and double-revoke the Google token).
    delete_account()'s steps are all delete-if-exists / best-effort, so if
    this call fails partway the row is left in "deleting" (still locked out)
    and a later retry safely resumes rather than redoing already-finished
    work.
    """
    tg_id = int(request.state.user["id"])
    if settings.OPERATOR_CHAT_ID is not None and tg_id == settings.OPERATOR_CHAT_ID:
        # get_user_status()/set_user_status() force the operator to "approved"
        # (src/database.py) — the "deleting" lock above would silently no-op
        # for this account, so refuse self-service deletion outright instead.
        raise HTTPException(status_code=403, detail="Operator account cannot be deleted")

    locked = await database.begin_account_deletion(tg_id)
    if not locked:
        # Another concurrent call already holds the lock and owns the
        # cleanup — the account is/will be gone either way, so report the
        # same success the winning call's caller will also see rather than
        # running delete_account() again.
        out = Response(status_code=204)
        out.delete_cookie(COOKIE_NAME, path="/", secure=settings.SESSION_COOKIE_SECURE)
        out.delete_cookie("ownix_preview", path="/", secure=settings.SESSION_COOKIE_SECURE)
        return out

    session_id = request.cookies.get(COOKIE_NAME)
    if session_id:
        await session_store.revoke(session_id)

    await delete_account(tg_id)

    out = Response(status_code=204)
    out.delete_cookie(COOKIE_NAME, path="/", secure=settings.SESSION_COOKIE_SECURE)
    out.delete_cookie("ownix_preview", path="/", secure=settings.SESSION_COOKIE_SECURE)
    return out
```

- [ ] **Step 8: Run test to verify it passes**

Run (PowerShell): `python -m pytest tests/test_auth.py::TestAccountDeletionLock::test_delete_account_route_short_circuits_when_already_deleting -v --timeout=60`
Expected: PASS.

- [ ] **Step 9: Run the scoped suite for regressions**

Run (PowerShell): `python -m pytest tests/test_auth.py tests/test_account.py tests/test_database.py -q --timeout=60`
Expected: all pass, including the pre-existing `test_delete_account_route_locks_and_revokes_session_before_cleanup_runs` and `test_delete_account_route_failure_leaves_lock_for_retry` tests (both still apply — they exercise the single-caller path, which `begin_account_deletion` still returns `True` for).

- [ ] **Step 10: Commit**

```bash
git add src/database.py src/api/auth.py tests/test_database.py tests/test_auth.py
git commit -m "fix(auth): make account-deletion lock compare-and-set to prevent duplicate concurrent deletes"
```

---

## Task 3: `_migrate_v43_v44` table rebuild is not atomic (Major #5)

**Files:**
- Modify: `src/database.py:1381-1409` (`_migrate_v43_v44`)
- Test: `tests/test_database.py`

**Finding:** The `users` table rebuild (`DROP TABLE IF EXISTS users_v44` → `CREATE TABLE users_v44` → `INSERT INTO users_v44 SELECT FROM users` → `DROP TABLE users` → `ALTER TABLE users_v44 RENAME TO users`) is not wrapped as one atomic transaction. Each DDL statement auto-commits as it runs; `PRAGMA user_version` only advances after `_run_migrations` fully returns (`src/database.py:1429-1431`). A crash between `DROP TABLE users` and the final `RENAME`, followed by a restart (which reruns the migration from `DROP TABLE IF EXISTS users_v44` since `user_version` wasn't bumped), destroys the only surviving copy of every user row.

**Note (scope guardrail):** This exact unwrapped-rebuild pattern is pre-existing convention shared by at least two earlier migrations in this file (`_migrate_v23_v24`'s `chat_state_v24` rebuild around line 1083-1101, and the `ignored_domains_v2` migration around line 645-646) — it is **not** unique to this PR. This task's scope is `_migrate_v43_v44` only. Fixing the older migrations' instances of the same pattern is a separate, out-of-scope repo-wide migration-safety pass — do not touch them.

Unlike `_migrate_v22_v23` (`src/database.py:1022-1054`), which toggles `PRAGMA foreign_keys=OFF` before its rebuild because `jobs` has `ON DELETE CASCADE` children that would otherwise cascade-delete on `DROP TABLE jobs`, `users` has no incoming foreign keys (confirmed: no `REFERENCES users` anywhere in `src/database.py`), so this fix only needs an explicit transaction, not FK toggling.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_database.py`:

```python
@pytest.mark.asyncio
async def test_migrate_v43_v44_rolls_back_atomically_on_failure(tmp_path, monkeypatch) -> None:
    """A crash between DROP TABLE users and the RENAME must not destroy the
    only surviving copy of every user row — the whole rebuild is one
    transaction, so a failure leaves the original `users` table intact for a
    safe retry on the next startup."""
    from src import database

    db_file = str(tmp_path / "v43_crash.db")
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    monkeypatch.setattr("src.database.settings.DB_PATH", db_file)

    async with aiosqlite.connect(db_file) as conn:
        await conn.execute(
            "CREATE TABLE users (tg_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT NOT NULL, "
            "last_name TEXT, photo_url TEXT, email TEXT, status TEXT NOT NULL DEFAULT 'pending', "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "CHECK(status IN ('pending','approved','blocked')))"
        )
        await conn.execute(
            "INSERT INTO users (tg_id, first_name, status) VALUES (1, 'Alice', 'approved')"
        )
        await conn.commit()

        # Fail the RENAME step, simulating a crash after DROP TABLE users.
        real_execute = conn.execute

        async def failing_execute(sql, *args, **kwargs):
            if "RENAME TO users" in sql:
                raise RuntimeError("simulated crash")
            return await real_execute(sql, *args, **kwargs)

        monkeypatch.setattr(conn, "execute", failing_execute)

        with pytest.raises(RuntimeError):
            await database._migrate_v43_v44(conn)

        monkeypatch.setattr(conn, "execute", real_execute)

        # The original users table (and Alice's row) must have survived —
        # not a half-renamed users_v44 shell.
        cur = await conn.execute("SELECT tg_id, first_name FROM users")
        rows = await cur.fetchall()
        assert [tuple(r) for r in rows] == [(1, "Alice")]

        cur = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users_v44'"
        )
        assert await cur.fetchone() is None, "the failed rebuild must not leave a stray users_v44 table"

    # A retry from the same starting state must still succeed cleanly.
    async with aiosqlite.connect(db_file) as conn2:
        await database._migrate_v43_v44(conn2)
        cur = await conn2.execute("PRAGMA table_info(users)")
        cols = {row[1] for row in await cur.fetchall()}
        assert "status" in cols
        cur = await conn2.execute("SELECT tg_id, first_name, status FROM users")
        assert await cur.fetchone() == (1, "Alice", "approved")
```

- [ ] **Step 2: Run test to verify it fails**

Run (PowerShell): `python -m pytest tests/test_database.py::test_migrate_v43_v44_rolls_back_atomically_on_failure -v --timeout=60`
Expected: FAIL — today's implementation leaves `users` already dropped (and no `users_v44` either, since the DROP already committed before the simulated RENAME failure), so the "original users table survived" assertion fails.

- [ ] **Step 3: Wrap the rebuild in an explicit transaction**

In `src/database.py`, change `_migrate_v43_v44`:

```python
# v43 → v44: widen users.status CHECK to add 'deleting' — the exclusivity lock
# self-serve account deletion holds while it runs, so every other account-write
# route (gated on status == 'approved') rejects concurrent writes during
# cleanup. SQLite can't ALTER a CHECK, so rebuild via selective column copy.
#
# The five DDL/DML statements below are wrapped in one explicit transaction:
# without BEGIN, each DDL statement auto-commits as it runs (PRAGMA
# user_version only advances after _run_migrations fully returns), so a
# crash between DROP TABLE users and the RENAME, followed by a restart,
# would rerun this migration from `DROP TABLE IF EXISTS users_v44` with the
# original `users` table already gone — destroying every user row. SQLite
# supports transactional DDL, so BEGIN/COMMIT/ROLLBACK make the whole
# rebuild all-or-nothing.
async def _migrate_v43_v44(conn: aiosqlite.Connection) -> None:
    await conn.execute("BEGIN IMMEDIATE")
    try:
        await conn.execute("DROP TABLE IF EXISTS users_v44")
        await conn.execute(
            """
            CREATE TABLE users_v44 (
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
            )
            """
        )
        await conn.execute(
            """
            INSERT INTO users_v44 (tg_id, username, first_name, last_name, photo_url,
                                    email, status, created_at, updated_at)
            SELECT tg_id, username, first_name, last_name, photo_url,
                   email, status, created_at, updated_at
              FROM users
            """
        )
        await conn.execute("DROP TABLE users")
        await conn.execute("ALTER TABLE users_v44 RENAME TO users")
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise


_MIGRATIONS.append(_migrate_v43_v44)
```

- [ ] **Step 4: Run test to verify it passes**

Run (PowerShell): `python -m pytest tests/test_database.py::test_migrate_v43_v44_rolls_back_atomically_on_failure -v --timeout=60`
Expected: PASS.

- [ ] **Step 5: Run the scoped suite for regressions**

Run (PowerShell): `python -m pytest tests/test_auth.py tests/test_account.py tests/test_database.py -q --timeout=60`
Expected: all pass, including the pre-existing `test_migration_creates_audit_log_and_triggers_directly` and `test_checklists_columns_are_added_to_v39_database` tests, both of which run `_run_migrations` across `_migrate_v43_v44` and must still land on the full target `user_version`.

- [ ] **Step 6: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "fix(database): wrap the v43→v44 users-table rebuild in one atomic transaction"
```

---

## Task 4: Destructive button appears before consequences on narrow viewports (Major #3)

**Files:**
- Modify: `web/app/(dashboard)/controls/page.tsx:472-497` (`DeleteAccountSection`)
- Test: `web/app/(dashboard)/controls/page.test.tsx`

**Finding:** `DeleteAccountSection` reuses the job/link-delete layout verbatim (`flex items-stretch gap-4 max-[620px]:flex-col`, button block first, divider, then the consequences `<p>`). On narrow viewports (`max-[620px]:flex-col`), flex-column stacking follows DOM order, so the destructive "Delete my account" button renders above the explanatory paragraph — but this is a full irreversible account wipe, not a single job delete, so the stakes are much higher than the sibling job/link-delete sections this layout was copied from.

- [ ] **Step 1: Write the failing test**

Add to `web/app/(dashboard)/controls/page.test.tsx` (this file already has the `section(title)` helper scoped to a `<details>` by its summary text — reuse it):

```tsx
it('renders the account-deletion consequences before the delete button in DOM order', () => {
  render(<ControlsPage />);
  const zone = section('Danger zone');
  // Regex, not a literal substring: the exact consequences wording is
  // hoisted into a shared constant in a later task and may change slightly
  // — this only needs to keep matching "roughly this sentence", not an
  // exact string, so it doesn't go stale when that happens.
  const consequences = zone.getByText(/deletes every job.*brain link.*domain rule/i);
  const button = zone.getByRole('button', { name: 'Delete my account' });
  // Node.DOCUMENT_POSITION_FOLLOWING (4): button comes after consequences.
  expect(
    consequences.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: FAIL — today the button block (containing "Delete my account") precedes the consequences paragraph in DOM order.

- [ ] **Step 3: Reorder the JSX**

In `web/app/(dashboard)/controls/page.tsx`, change the `return` of `DeleteAccountSection` so the consequences paragraph comes first:

```tsx
  return (
    <div className="flex items-stretch gap-4 max-[620px]:flex-col">
      <p className="text-sm text-body">
        Deletes every job, Brain link, tag, and domain rule tied to your
        account, disconnects Google, and revokes your session. This
        cannot be undone.
      </p>
      <div className="border-l border-line max-[620px]:hidden" />
      <div className="flex-shrink-0">
        <ConfirmDialog
          title="Permanently delete your account?"
          description="This deletes every job, Brain link, tag, and domain rule you own, disconnects Google, and revokes your session. This can't be undone."
          confirmLabel="Delete my account"
          pending={deleting}
          onConfirm={handleDelete}
          trigger={
            <button className="h-8 rounded-md border border-line px-3 text-button font-medium text-status-error transition-ui hover:bg-raised">
              Delete my account
            </button>
          }
        />
        {error && (
          <p className="mt-2 text-xs text-status-error">{error}</p>
        )}
      </div>
    </div>
  );
```

Only the order of the three top-level children changed (paragraph, divider, button block) — no text or class changes yet (those come in later tasks). This only reorders `DeleteAccountSection`; the sibling job/link-delete sections (`jobs/[id]/page.tsx`, `links-table.tsx`) are unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run the full frontend suite for regressions**

Run (from `web/`): `npm run test:run`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add web/app/\(dashboard\)/controls/page.tsx web/app/\(dashboard\)/controls/page.test.tsx
git commit -m "fix(controls): show account-deletion consequences before the delete button"
```

---

## Task 5: Hand-rolled fetch swallows the server's error detail (Major #4)

**Files:**
- Modify: `web/app/(dashboard)/controls/page.tsx:1-25` (imports), `459-470` (`handleDelete`)
- Test: `web/app/(dashboard)/controls/page.test.tsx`

**Finding:** `handleDelete` hand-rolls `fetch('/api/auth/me', {method:'DELETE'})` + `res.ok` check + a generic thrown `Error('Could not delete account')`, discarding whatever `detail` message the server actually returns (e.g. a validation or conflict error). `apiDelete(url, fallback)`, already exported from `web/lib/fetch-utils.ts:177` and already used by `useTagList`/`useTemplateList`, does exactly this correctly — it parses `res.json().detail` on failure and only falls back to the generic message when there is no `detail`.

**Interfaces:**
- Consumes: `apiDelete(url: string, fallback?: string): Promise<void>` from `web/lib/fetch-utils.ts` — throws `Error(detail ?? fallback)` on a non-2xx response.

- [ ] **Step 1: Write the failing test**

Add to `web/app/(dashboard)/controls/page.test.tsx`:

```tsx
it('shows the server-provided error detail when account deletion fails', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ detail: 'Cannot delete: Google disconnect failed' }), { status: 502 }),
  ));
  render(<ControlsPage />);
  const zone = section('Danger zone');
  fireEvent.click(zone.getByRole('button', { name: 'Delete my account' }));
  const dialog = within(screen.getByRole('dialog'));
  fireEvent.click(dialog.getByRole('button', { name: 'Delete my account' }));
  await waitFor(() =>
    expect(zone.getByText('Cannot delete: Google disconnect failed')).toBeTruthy(),
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: FAIL — today's `handleDelete` throws the generic `'Could not delete account'` regardless of the response body, so the server's specific `detail` text never renders.

- [ ] **Step 3: Use `apiDelete`**

In `web/app/(dashboard)/controls/page.tsx`, change the import:

```tsx
import { apiDelete, apiPut } from '@/lib/fetch-utils';
```

And change `handleDelete`:

```tsx
  const handleDelete = async () => {
    setDeleting(true);
    setError(undefined);
    try {
      await apiDelete('/api/auth/me', 'Could not delete account');
      router.replace('/login');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete account');
      setDeleting(false);
    }
  };
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run the full frontend suite for regressions**

Run (from `web/`): `npm run test:run`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add web/app/\(dashboard\)/controls/page.tsx web/app/\(dashboard\)/controls/page.test.tsx
git commit -m "fix(controls): surface the server's real error detail on account-delete failure"
```

---

## Task 6: Extract the duplicated "resume stuck deletion" block (Minor #6)

**Files:**
- Modify: `src/api/auth.py:48-67` (`_login_telegram_user`), `104-125` (`miniapp_session`)
- Test: `tests/test_auth.py`

**Finding:** The block `if await database.get_user_status(...) == "deleting": await delete_account(...); log.info("auth.resumed_account_deletion", ...); return {"ok": True, "account_deleted": True}` is duplicated verbatim across `_login_telegram_user` (lines 64-67) and `miniapp_session` (lines 122-125), differing only in the local variable name (`payload.id` vs `chat_id`).

**Note:** `redeem_handoff_login` (fixed in Task 1) is **not** included in this extraction — it raises an `HTTPException` and redirects rather than returning a `{"ok": ..., "account_deleted": ...}` session dict, so the shared helper's `dict | None` return contract doesn't fit its shape. It keeps its own inline check as written in Task 1.

**Interfaces:**
- Produces: `_resume_deletion_if_stuck(tg_id: int) -> dict | None` — returns the response body to send back if a stuck deletion was resumed, or `None` to mean "continue with normal login."

- [ ] **Step 1: Write the failing test**

This is a pure refactor (behavior must be unchanged), so the test asserts both call sites still resume correctly through the shared helper. Add to `tests/test_auth.py`, near the top-level test functions (not inside a class), following the style of the existing `test_login_resumes_stuck_deletion_instead_of_minting_session`:

```python
def test_resume_deletion_helper_is_used_by_both_login_paths() -> None:
    """_login_telegram_user and miniapp_session must both resume a stuck
    deletion through the same shared helper, not duplicated inline logic."""
    import inspect

    from src.api import auth as auth_api

    assert callable(auth_api._resume_deletion_if_stuck)
    login_src = inspect.getsource(auth_api._login_telegram_user)
    miniapp_src = inspect.getsource(auth_api.miniapp_session)
    assert "_resume_deletion_if_stuck" in login_src
    assert "_resume_deletion_if_stuck" in miniapp_src
```

- [ ] **Step 2: Run test to verify it fails**

Run (PowerShell): `python -m pytest tests/test_auth.py::test_resume_deletion_helper_is_used_by_both_login_paths -v --timeout=60`
Expected: FAIL — `_resume_deletion_if_stuck` does not exist yet, and neither function currently calls it.

- [ ] **Step 3: Extract the helper and call it from both sites**

In `src/api/auth.py`, add the helper just above `_login_telegram_user`:

```python
async def _resume_deletion_if_stuck(tg_id: int) -> dict | None:
    """Finish a deletion left mid-flight instead of minting a session into a
    half-deleted account (a prior /api/auth/me DELETE that failed partway,
    e.g. a network blip during Google token cleanup, still reads "deleting"
    here). Returns the response body to send back if a stuck deletion was
    resumed, or None to mean "continue with normal login". Every step in
    delete_account() is delete-if-exists / best-effort, so resuming is safe
    even if a previous call finished some steps already.
    """
    if await database.get_user_status(tg_id) != "deleting":
        return None
    await delete_account(tg_id)
    log.info("auth.resumed_account_deletion", tg_id=tg_id)
    return {"ok": True, "account_deleted": True}
```

Change `_login_telegram_user`, replacing lines 59-67:

```python
    resumed = await _resume_deletion_if_stuck(payload.id)
    if resumed is not None:
        return resumed
```

Change `miniapp_session`, replacing lines 120-125:

```python
    resumed = await _resume_deletion_if_stuck(chat_id)
    if resumed is not None:
        return resumed
```

- [ ] **Step 4: Run test to verify it passes**

Run (PowerShell): `python -m pytest tests/test_auth.py::test_resume_deletion_helper_is_used_by_both_login_paths -v --timeout=60`
Expected: PASS.

- [ ] **Step 5: Run the scoped suite for regressions**

Run (PowerShell): `python -m pytest tests/test_auth.py tests/test_account.py tests/test_database.py -q --timeout=60`
Expected: all pass, including the pre-existing `test_login_resumes_stuck_deletion_instead_of_minting_session` (exercises `_login_telegram_user`'s path through the new helper) — this confirms the extraction preserved behavior.

- [ ] **Step 6: Commit**

```bash
git add src/api/auth.py tests/test_auth.py
git commit -m "refactor(auth): extract duplicated resume-stuck-deletion logic into a shared helper"
```

---

## Task 7: No extra confirmation friction on the highest-stakes destructive action (Minor #7)

**Files:**
- Modify: `web/components/ui/confirm-dialog.tsx` (add optional `confirmDisabled` prop)
- Modify: `web/app/(dashboard)/controls/page.tsx` (`DeleteAccountSection`)
- Test: `web/components/ui/confirm-dialog.test.tsx`, `web/app/(dashboard)/controls/page.test.tsx`

**Finding:** `DeleteAccountSection` uses the same single-click-to-open/single-click-to-confirm flow as deleting one job, for the app's highest-stakes destructive action (a full irreversible account wipe). `ConfirmDialog` already supports extra interactive `children` (the opt-in checkbox pattern at `web/app/(dashboard)/jobs/[id]/page.tsx:1308-1328`), but that pattern only supplies an extra *value* to the caller's `onConfirm` — it doesn't gate the confirm button's own enabled state. Add a type-to-confirm text field that does gate it, reusing the existing `children` slot rather than building a new component.

**Interfaces:**
- Produces: `ConfirmDialog`'s new optional prop `confirmDisabled?: boolean` (default `false`) — when `true`, the confirm button is disabled in addition to the existing `pending` disable.

- [ ] **Step 1: Write the failing test (ConfirmDialog prop)**

Add to `web/components/ui/confirm-dialog.test.tsx`:

```tsx
  it('disables the confirm button when confirmDisabled is true', async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        trigger={<button>Delete job</button>}
        title="Delete?"
        description="Cannot be undone"
        confirmLabel="Delete permanently"
        confirmDisabled
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Delete job' }));
    const confirmButton = await screen.findByRole('button', { name: 'Delete permanently' });
    expect(confirmButton).toBeDisabled();
    fireEvent.click(confirmButton);
    expect(onConfirm).not.toHaveBeenCalled();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `npm run test:run -- confirm-dialog.test.tsx`
Expected: FAIL — TypeScript will reject the unknown `confirmDisabled` prop, or (if TS errors don't fail the test run) the button renders enabled.

- [ ] **Step 3: Add `confirmDisabled` to `ConfirmDialog`**

In `web/components/ui/confirm-dialog.tsx`, change the props type and the button:

```tsx
type ConfirmDialogProps = {
  trigger: ReactNode;
  title: string;
  description: string;
  confirmLabel: string;
  pending?: boolean;
  /** Disable the confirm button independent of `pending` — e.g. a
   * type-to-confirm field that hasn't matched yet. */
  confirmDisabled?: boolean;
  onConfirm: () => void | Promise<void>;
  /** Extra interactive content (e.g. an opt-in checkbox) between the
   * description and the action buttons. */
  children?: ReactNode;
};

export function ConfirmDialog({
  trigger,
  title,
  description,
  confirmLabel,
  pending = false,
  confirmDisabled = false,
  onConfirm,
  children,
}: ConfirmDialogProps) {
```

And the confirm `<button>`:

```tsx
          <button
            type="button"
            disabled={pending || confirmDisabled}
            onClick={async () => {
              await onConfirm();
              setOpen(false);
            }}
            className="h-8 rounded-md bg-status-error px-3 text-button font-medium text-[#1b1309] transition-ui hover:brightness-110 disabled:opacity-50"
          >
            {pending ? 'Deleting…' : confirmLabel}
          </button>
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `web/`): `npm run test:run -- confirm-dialog.test.tsx`
Expected: PASS.

- [ ] **Step 5: Write the failing test (Controls page)**

Add to `web/app/(dashboard)/controls/page.test.tsx`:

```tsx
it('keeps the account-delete confirm button disabled until "delete" is typed', async () => {
  render(<ControlsPage />);
  const zone = section('Danger zone');
  fireEvent.click(zone.getByRole('button', { name: 'Delete my account' }));

  const dialog = within(screen.getByRole('dialog'));
  const confirmButton = dialog.getByRole('button', { name: 'Delete my account' });
  expect(confirmButton).toBeDisabled();

  fireEvent.change(dialog.getByLabelText('Type delete to confirm'), {
    target: { value: 'delete' },
  });
  expect(confirmButton).not.toBeDisabled();
});
```

- [ ] **Step 6: Run test to verify it fails**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: FAIL — `DeleteAccountSection` doesn't render a type-to-confirm input yet, so `getByLabelText` throws.

- [ ] **Step 7: Add the type-to-confirm field to `DeleteAccountSection`**

In `web/app/(dashboard)/controls/page.tsx`, change `DeleteAccountSection`:

```tsx
function DeleteAccountSection() {
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [confirmText, setConfirmText] = useState('');

  const handleDelete = async () => {
    setDeleting(true);
    setError(undefined);
    try {
      await apiDelete('/api/auth/me', 'Could not delete account');
      router.replace('/login');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete account');
      setDeleting(false);
    }
  };

  return (
    <div className="flex items-stretch gap-4 max-[620px]:flex-col">
      <p className="text-sm text-body">
        Deletes every job, Brain link, tag, and domain rule tied to your
        account, disconnects Google, and revokes your session. This
        cannot be undone.
      </p>
      <div className="border-l border-line max-[620px]:hidden" />
      <div className="flex-shrink-0">
        <ConfirmDialog
          title="Permanently delete your account?"
          description="This deletes every job, Brain link, tag, and domain rule you own, disconnects Google, and revokes your session. This can't be undone."
          confirmLabel="Delete my account"
          pending={deleting}
          confirmDisabled={confirmText.trim().toLowerCase() !== 'delete'}
          onConfirm={handleDelete}
          trigger={
            <button className="h-8 rounded-md border border-line px-3 text-button font-medium text-status-error transition-ui hover:bg-raised">
              Delete my account
            </button>
          }
        >
          <label className="flex flex-col gap-1 text-xs text-body">
            Type <span className="font-mono font-semibold text-ink">delete</span> to confirm
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              autoComplete="off"
              className="w-full rounded-md border border-line bg-canvas px-3 py-1.5 text-sm text-ink placeholder-muted focus:border-signal focus:outline-none"
            />
          </label>
        </ConfirmDialog>
        {error && (
          <p className="mt-2 text-xs text-status-error">{error}</p>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 8: Run test to verify it passes**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: PASS.

- [ ] **Step 9: Run the full frontend suite for regressions**

Run (from `web/`): `npm run test:run`
Expected: all pass — confirm `jobs/[id]/page.tsx`'s and `links-table.tsx`'s `ConfirmDialog` usages still work unchanged (they don't pass `confirmDisabled`, so it defaults to `false`, preserving current behavior).

- [ ] **Step 10: Commit**

```bash
git add web/components/ui/confirm-dialog.tsx web/components/ui/confirm-dialog.test.tsx web/app/\(dashboard\)/controls/page.tsx web/app/\(dashboard\)/controls/page.test.tsx
git commit -m "feat(controls): require typing \"delete\" to confirm account deletion"
```

---

## Task 8: Confirm label duplicates the trigger label verbatim (Minor #8)

**Files:**
- Modify: `web/app/(dashboard)/controls/page.tsx` (`DeleteAccountSection`)
- Test: `web/app/(dashboard)/controls/page.test.tsx`

**Finding:** `confirmLabel="Delete my account"` (line 478) duplicates the trigger button's own label verbatim (line 483). Sibling patterns use a distinct, more final-sounding label — `jobs/[id]/page.tsx:1300` uses `confirmLabel="Delete permanently"` for a trigger labeled `"Delete job"`.

- [ ] **Step 1: Write the failing test**

Update the test added in Task 7 Step 5 (`keeps the account-delete confirm button disabled until "delete" is typed`) in `web/app/(dashboard)/controls/page.test.tsx` — the confirm button's accessible name changes, so the query must change too:

```tsx
it('keeps the account-delete confirm button disabled until "delete" is typed', async () => {
  render(<ControlsPage />);
  const zone = section('Danger zone');
  fireEvent.click(zone.getByRole('button', { name: 'Delete my account' }));

  const dialog = within(screen.getByRole('dialog'));
  const confirmButton = dialog.getByRole('button', { name: 'Yes, delete my account' });
  expect(confirmButton).toBeDisabled();

  fireEvent.change(dialog.getByLabelText('Type delete to confirm'), {
    target: { value: 'delete' },
  });
  expect(confirmButton).not.toBeDisabled();
});
```

Also update the Task 5 test (`shows the server-provided error detail when account deletion fails`) to use the dialog's confirm button by its new label, and to type the confirm text first (Task 7 gates it):

```tsx
it('shows the server-provided error detail when account deletion fails', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ detail: 'Cannot delete: Google disconnect failed' }), { status: 502 }),
  ));
  render(<ControlsPage />);
  const zone = section('Danger zone');
  fireEvent.click(zone.getByRole('button', { name: 'Delete my account' }));
  const dialog = within(screen.getByRole('dialog'));
  fireEvent.change(dialog.getByLabelText('Type delete to confirm'), { target: { value: 'delete' } });
  fireEvent.click(dialog.getByRole('button', { name: 'Yes, delete my account' }));
  await waitFor(() =>
    expect(zone.getByText('Cannot delete: Google disconnect failed')).toBeTruthy(),
  );
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: FAIL — no button named "Yes, delete my account" exists yet.

- [ ] **Step 3: Change the confirm label**

In `web/app/(dashboard)/controls/page.tsx`, in `DeleteAccountSection`'s `<ConfirmDialog>`, change:

```tsx
          confirmLabel="Delete my account"
```

to:

```tsx
          confirmLabel="Yes, delete my account"
```

(The trigger button's own label, `"Delete my account"`, is unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run the full frontend suite for regressions**

Run (from `web/`): `npm run test:run`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add web/app/\(dashboard\)/controls/page.tsx web/app/\(dashboard\)/controls/page.test.tsx
git commit -m "fix(controls): distinguish the account-delete confirm label from its trigger"
```

---

## Task 9: Delete-failure error isn't a live region (Minor #9)

**Files:**
- Modify: `web/app/(dashboard)/controls/page.tsx` (`DeleteAccountSection`)
- Test: `web/app/(dashboard)/controls/page.test.tsx`

**Finding:** The delete-failure error `<p>` (line 487-489) isn't a `role="alert"` live region. The analogous error paragraph in `web/components/feed/links-table.tsx:522` does use `role="alert"`.

- [ ] **Step 1: Write the failing test**

Add to `web/app/(dashboard)/controls/page.test.tsx`:

```tsx
it('announces the account-delete error as an alert', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ detail: 'Cannot delete right now' }), { status: 502 }),
  ));
  render(<ControlsPage />);
  const zone = section('Danger zone');
  fireEvent.click(zone.getByRole('button', { name: 'Delete my account' }));
  const dialog = within(screen.getByRole('dialog'));
  fireEvent.change(dialog.getByLabelText('Type delete to confirm'), { target: { value: 'delete' } });
  fireEvent.click(dialog.getByRole('button', { name: 'Yes, delete my account' }));
  await waitFor(() => expect(zone.getByRole('alert')).toHaveTextContent('Cannot delete right now'));
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: FAIL — `getByRole('alert')` finds nothing, since the error `<p>` has no `role`.

- [ ] **Step 3: Add `role="alert"`**

In `web/app/(dashboard)/controls/page.tsx`, in `DeleteAccountSection`, change:

```tsx
        {error && (
          <p className="mt-2 text-xs text-status-error">{error}</p>
        )}
```

to:

```tsx
        {error && (
          <p
            className="mt-2 text-xs text-status-error"
            role="alert"
          >
            {error}
          </p>
        )}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run the full frontend suite for regressions**

Run (from `web/`): `npm run test:run`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add web/app/\(dashboard\)/controls/page.tsx web/app/\(dashboard\)/controls/page.test.tsx
git commit -m "fix(controls): announce account-delete failure as an accessible alert"
```

---

## Task 10: Dialog closes even when delete fails (Minor #10)

**Files:**
- Modify: `web/app/(dashboard)/controls/page.tsx` (`DeleteAccountSection.handleDelete`)
- Test: `web/app/(dashboard)/controls/page.test.tsx`

**Finding:** `handleDelete` catches its own errors and never rethrows, so `ConfirmDialog`'s `onClick` (`await onConfirm(); setOpen(false);`) closes the dialog unconditionally even when the delete failed — reads as "nothing happened." This is a pre-existing app-wide `ConfirmDialog` usage quirk (same in `links-table.tsx`, `jobs/[id]/page.tsx`), not a regression, but the stakes are highest here.

**Investigated (per plan caveat):** Read `web/components/ui/confirm-dialog.tsx`'s confirm-button `onClick` — `async () => { await onConfirm(); setOpen(false); }`. It has no `try`/`catch`: if `onConfirm()` throws, `setOpen(false)` is never reached (the `await` re-throws out of the async arrow function before that line runs), so the dialog correctly stays open. The only side effect is a benign unhandled-promise-rejection console warning, since nothing awaits this onClick's returned promise — no functional issue. This means the fix is entirely local to `DeleteAccountSection.handleDelete` (rethrow on failure); `ConfirmDialog` itself does not need to change, so the sibling call sites (`links-table.tsx`, `jobs/[id]/page.tsx`) are unaffected, matching the smaller of the two options the finding lays out.

- [ ] **Step 1: Write the failing test**

Add to `web/app/(dashboard)/controls/page.test.tsx`:

```tsx
it('keeps the confirm dialog open when account deletion fails', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ detail: 'Cannot delete: 3 jobs still processing' }), { status: 409 }),
  ));
  render(<ControlsPage />);
  const zone = section('Danger zone');
  fireEvent.click(zone.getByRole('button', { name: 'Delete my account' }));
  const dialog = within(screen.getByRole('dialog'));
  fireEvent.change(dialog.getByLabelText('Type delete to confirm'), { target: { value: 'delete' } });
  fireEvent.click(dialog.getByRole('button', { name: 'Yes, delete my account' }));

  await waitFor(() =>
    expect(zone.getByText('Cannot delete: 3 jobs still processing')).toBeTruthy(),
  );
  // The dialog itself must still be mounted — a silent close would read as
  // "nothing happened" on the highest-stakes destructive action in the app.
  expect(screen.getByRole('dialog')).toBeTruthy();
  expect(screen.getByText('Permanently delete your account?')).toBeTruthy();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: FAIL — today's `handleDelete` swallows the error, so `ConfirmDialog`'s `onClick` reaches `setOpen(false)` and the dialog unmounts.

- [ ] **Step 3: Rethrow the error**

In `web/app/(dashboard)/controls/page.tsx`, change `handleDelete`:

```tsx
  const handleDelete = async () => {
    setDeleting(true);
    setError(undefined);
    try {
      await apiDelete('/api/auth/me', 'Could not delete account');
      router.replace('/login');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete account');
      setDeleting(false);
      throw err;
    }
  };
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run the full frontend suite for regressions**

Run (from `web/`): `npm run test:run`
Expected: all pass — confirm the Task 5 success-path test (`router.replace('/login')`) still passes too, since a successful `apiDelete` doesn't hit the `catch` branch at all.

- [ ] **Step 6: Commit**

```bash
git add web/app/\(dashboard\)/controls/page.tsx web/app/\(dashboard\)/controls/page.test.tsx
git commit -m "fix(controls): keep the confirm dialog open when account deletion fails"
```

---

## Task 11: Redundant per-job DB round trip in the deletion loop (Minor #11)

**Files:**
- Modify: `src/services/account.py:19-27` (`delete_account`)
- Test: `tests/test_account.py`

**Finding:** The per-job loop (`get_job()` → `build_job_purge_task()` [which itself calls `list_document_outputs()`] → `delete_job()`) runs synchronously inside the `DELETE /api/auth/me` request, opening/closing a fresh SQLite connection per DB call per job — real latency/timeout risk for accounts with "hundreds" of jobs (per `delete_job`'s own docstring). At minimum, drop the redundant `get_job()` call by selecting only the columns `build_job_purge_task` actually needs directly from the initial bulk query.

**Note (scope guardrail):** `build_job_purge_task(job)` (`src/services/jobs.py:48-70`) reads `job["id"]`, `job["chat_id"]`, `job.get("drive_url")`, `job.get("prd_auto_drive_file_id")`, `job.get("prd_intent_drive_file_id")`, `job.get("url")`, and internally calls `database.list_document_outputs(job["id"])` (a separate, unavoidable query per job — not touched here). `database.delete_job()` manages its own `connection()` internally with no injectable-connection parameter, so reusing a single connection across the whole loop (the other half of the finding's suggested fix) would require changing `delete_job()`'s signature — out of proportion for this fix, so this task implements only the `get_job()` elimination. Do NOT move this to the worker/queue in this task — that's a larger architectural change; it is a documented follow-up, not part of this plan.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_account.py` (reuses the existing `account_db` fixture and `CHAT_ID` constant already defined in this file):

```python
def test_delete_account_does_not_refetch_each_job_individually(account_db, monkeypatch) -> None:
    """The purge-task loop must build its payload from the initial bulk
    query, not re-fetch each job row with database.get_job() (an extra
    round trip per job that matters at "hundreds of jobs" scale)."""
    from src.services import account as account_module

    database = account_db
    calls: list[str] = []
    real_get_job = database.get_job

    async def spy_get_job(job_id: str):
        calls.append(job_id)
        return await real_get_job(job_id)

    monkeypatch.setattr(account_module.database, "get_job", spy_get_job)

    asyncio.run(account_module.delete_account(CHAT_ID))

    assert calls == []
    assert asyncio.run(database.get_user(CHAT_ID)) is None
    row = asyncio.run(database._fetch_one("SELECT 1 FROM purge_tasks WHERE job_id = 'job_1'"))
    assert row is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run (PowerShell): `python -m pytest tests/test_account.py::test_delete_account_does_not_refetch_each_job_individually -v --timeout=60`
Expected: FAIL — `calls` is `['job_1']`, not `[]`, since today's loop calls `database.get_job(row["id"])` for every job.

- [ ] **Step 3: Select the needed columns directly and drop `get_job()`**

In `src/services/account.py`, change the job loop in `delete_account`:

```python
async def delete_account(chat_id: int) -> None:
    """Hard-delete every job, link, credential, and setting chat_id owns."""
    # Select exactly the columns build_job_purge_task() needs directly from
    # the bulk query, instead of re-fetching each job row individually with
    # database.get_job() — that was an extra SQLite connection open/close per
    # job on top of the delete_job() call already needed for it.
    job_rows = await database._fetch_dicts(
        "SELECT id, chat_id, url, drive_url, prd_auto_drive_file_id, prd_intent_drive_file_id "
        "FROM jobs WHERE chat_id = ?",
        (chat_id,),
    )
    for row in job_rows:
        purge_task = await build_job_purge_task(row)
        await database.delete_job(row["id"], purge_payload=purge_task, with_links=True)

    # Standalone links (e.g. bookmark imports) not tied to a job deleted above.
    link_rows = await database._fetch_dicts("SELECT id FROM links WHERE chat_id = ?", (chat_id,))
    for row in link_rows:
        await database.delete_link(row["id"], chat_id)

    for token in await extension_tokens.list_extension_tokens(chat_id):
        await extension_tokens.revoke_extension_token(chat_id, token["id"])

    await disconnect_google(chat_id)
    await database.delete_account_settings(chat_id)
    await database.clear_chat_state(chat_id)
    await database.delete_user(chat_id)
    log.info("account_deleted", chat_id=chat_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run (PowerShell): `python -m pytest tests/test_account.py::test_delete_account_does_not_refetch_each_job_individually -v --timeout=60`
Expected: PASS.

- [ ] **Step 5: Run the scoped suite for regressions**

Run (PowerShell): `python -m pytest tests/test_auth.py tests/test_account.py tests/test_database.py -q --timeout=60`
Expected: all pass, including the pre-existing `test_delete_account_removes_every_owned_row` and `test_delete_account_is_scoped_to_the_caller` (both exercise the same loop with the new query).

- [ ] **Step 6: Commit**

```bash
git add src/services/account.py tests/test_account.py
git commit -m "perf(account): drop redundant per-job get_job() call in delete_account"
```

---

## Task 12: In-flight queued jobs aren't dequeued before their rows are deleted (Minor #12)

**Files:**
- Modify: `src/services/account.py:19-27` (`delete_account`)
- Test: none (comment-only change; the scoped suite run below is the verification step)

**Finding:** Jobs still `pending`/`processing`/enqueued in Redis (`video_jobs` list) aren't dequeued or cancelled before their rows are deleted by `delete_account()`.

**Investigated (per plan caveat):** Read `src/worker.py`'s job-loading path. `_load_job_or_log(job_id)` (`src/worker.py:35-40`) calls `database.get_job(job_id)`, and every task handler (`_handle_video` at line 65-69, the generic handler, the bookmarks handler, and the `unknown_task` fallback at line 330-339) checks `if not job: return` / logs `"job_gone_skipped"` and returns immediately — no crash, no downstream write against a missing job id, just a logged no-op. This confirms the finding's own hedge ("not a crash... verify this is actually true") is correct: the worker already handles a missing job gracefully. Per the finding's explicit instruction to "choose the smaller of these two [fixes] unless dequeuing turns out to be a two-line addition" — it isn't (Redis's `video_jobs` list has no per-item removal-by-content primitive without an `LREM`-and-race-prone scan across every pending task, none of which this codebase currently does anywhere) — this task adds the documenting comment only.

- [ ] **Step 1: Add the documenting comment**

In `src/services/account.py`, add a comment above the job loop in `delete_account` (this lands just above the loop introduced/kept by Task 11 — apply after Task 11 if executing in order):

```python
    # Jobs still pending/processing and already enqueued in Redis (video_jobs)
    # are not dequeued here. When the worker eventually pops that task,
    # _load_job_or_log() (src/worker.py) finds the row gone and every handler
    # no-ops with a logged "job_gone_skipped" / "job_not_found" rather than
    # crashing or writing to a missing job id — verified by reading
    # src/worker.py's dispatch handlers. Actually dequeuing mid-request would
    # need a scan-and-remove across the whole Redis list with no atomic
    # removal-by-content primitive available; not worth it for a case the
    # worker already handles safely.
    job_rows = await database._fetch_dicts(
        "SELECT id, chat_id, url, drive_url, prd_auto_drive_file_id, prd_intent_drive_file_id "
        "FROM jobs WHERE chat_id = ?",
        (chat_id,),
    )
```

(The rest of `delete_account` is unchanged — this only adds the comment directly above the existing `job_rows = ...` query line from Task 11.)

- [ ] **Step 2: Run the scoped suite for regressions**

Run (PowerShell): `python -m pytest tests/test_auth.py tests/test_account.py tests/test_database.py -q --timeout=60`
Expected: all pass (comment-only change — this run is purely a regression check, no new behavior to assert).

- [ ] **Step 3: Commit**

```bash
git add src/services/account.py
git commit -m "docs(account): explain why in-flight queued jobs are not dequeued on account deletion"
```

---

## Task 13: `user_deleted` log fires unconditionally regardless of outcome (Minor #13)

**Files:**
- Modify: `src/database.py:2243-2247` (`delete_user`)
- Test: `tests/test_database.py`

**Finding:** `log.info("user_deleted", tg_id=tg_id)` (line 2246) fires unconditionally even when `deleted` is `False` (the row didn't exist), which is misleading regardless of exactly which call path reaches it with `deleted=False`.

**Investigated (per plan caveat):** `delete_user` is the last step of `delete_account()` (`src/services/account.py`), so on a single, uninterrupted `delete_account()` run it's only ever called once with a row that does exist. The `deleted=False` case is reachable on a genuine resume-on-login retry only if a prior attempt got as far as `delete_user()` before failing on something after it — currently nothing runs after it, so in today's code `deleted=False` mainly shows up if `delete_user` is ever called directly against an unknown/already-gone `tg_id` (e.g. a retry after a partial failure elsewhere doesn't skip re-calling it, or a future caller). Regardless of exact reachability, logging `deleted` unconditionally as `True`-implied text when it may be `False` is misleading on its face — fix applies either way.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_database.py`:

```python
@pytest.mark.asyncio
async def test_delete_user_logs_deleted_flag_when_row_is_missing(tmp_path, monkeypatch) -> None:
    """delete_user's log line must report whether a row was actually
    removed, not fire the same unconditional message either way."""
    from src import database

    db_file = str(tmp_path / "delete_user_log.db")
    monkeypatch.setattr("src.config.settings.DB_PATH", db_file)
    monkeypatch.setattr("src.database.settings.DB_PATH", db_file)
    await database.init_db()

    logged: dict = {}

    def fake_info(event, **kwargs):
        logged["event"] = event
        logged["kwargs"] = kwargs

    monkeypatch.setattr(database.log, "info", fake_info)

    result = await database.delete_user(999999)

    assert result is False
    assert logged["event"] == "user_deleted"
    assert logged["kwargs"].get("deleted") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run (PowerShell): `python -m pytest tests/test_database.py::test_delete_user_logs_deleted_flag_when_row_is_missing -v --timeout=60`
Expected: FAIL — today's log call has no `deleted` kwarg at all, so `logged["kwargs"].get("deleted")` is `None`, not `False`.

- [ ] **Step 3: Log the `deleted` flag**

In `src/database.py`, change `delete_user`:

```python
async def delete_user(tg_id: int) -> bool:
    """Hard-delete the invite-gate row for tg_id (account deletion's last step)."""
    deleted = await _execute_rowcount("DELETE FROM users WHERE tg_id = ?", (tg_id,)) > 0
    log.info("user_deleted", tg_id=tg_id, deleted=deleted)
    return deleted
```

- [ ] **Step 4: Run test to verify it passes**

Run (PowerShell): `python -m pytest tests/test_database.py::test_delete_user_logs_deleted_flag_when_row_is_missing -v --timeout=60`
Expected: PASS.

- [ ] **Step 5: Run the scoped suite for regressions**

Run (PowerShell): `python -m pytest tests/test_auth.py tests/test_account.py tests/test_database.py -q --timeout=60`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "fix(database): log delete_user's actual outcome instead of an unconditional message"
```

---

## Task 14: Duplicated consequences copy (Nit #14)

**Files:**
- Modify: `web/app/(dashboard)/controls/page.tsx` (`DeleteAccountSection`)
- Test: `web/app/(dashboard)/controls/page.test.tsx`

**Finding:** `ConfirmDialog`'s `description` prop and the adjacent static `<p>` restate the same consequences in near-identical wording as two separate string literals a few lines apart (`"This deletes every job, Brain link, tag, and domain rule you own, disconnects Google, and revokes your session. This can't be undone."` vs `"Deletes every job, Brain link, tag, and domain rule tied to your account, disconnects Google, and revokes your session. This cannot be undone."`).

- [ ] **Step 1: Write the failing test**

Add to `web/app/(dashboard)/controls/page.test.tsx` — this asserts the same copy string appears in both places (the dialog description and the static paragraph), which only holds once a single constant is reused:

```tsx
it('uses the same consequences copy in the dialog description and the static paragraph', () => {
  render(<ControlsPage />);
  const zone = section('Danger zone');
  fireEvent.click(zone.getByRole('button', { name: 'Delete my account' }));
  const dialogText = screen.getByRole('dialog').textContent ?? '';
  const staticParagraph = zone.getByText(/deletes every job, brain link, tag, and domain rule/i);
  expect(dialogText).toContain(staticParagraph.textContent);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: FAIL — the dialog description and the static paragraph currently have different wording, so the dialog's text does not contain the paragraph's exact text.

- [ ] **Step 3: Hoist a shared constant**

In `web/app/(dashboard)/controls/page.tsx`, add a module-level constant just above `DeleteAccountSection`:

```tsx
const DELETE_ACCOUNT_CONSEQUENCES =
  "This deletes every job, Brain link, tag, and domain rule you own, disconnects Google, and revokes your session. This can't be undone.";

function DeleteAccountSection() {
```

Then use it in both places inside `DeleteAccountSection`:

```tsx
      <p className="text-sm text-body">
        {DELETE_ACCOUNT_CONSEQUENCES}
      </p>
      <div className="border-l border-line max-[620px]:hidden" />
      <div className="flex-shrink-0">
        <ConfirmDialog
          title="Permanently delete your account?"
          description={DELETE_ACCOUNT_CONSEQUENCES}
          confirmLabel="Yes, delete my account"
          pending={deleting}
          confirmDisabled={confirmText.trim().toLowerCase() !== 'delete'}
          onConfirm={handleDelete}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run the full frontend suite for regressions**

Run (from `web/`): `npm run test:run`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add web/app/\(dashboard\)/controls/page.tsx web/app/\(dashboard\)/controls/page.test.tsx
git commit -m "refactor(controls): dedupe account-deletion consequences copy into one constant"
```

---

## Task 15: "Danger zone" header has no visual differentiation (Nit #15)

**Files:**
- Modify: `web/app/(dashboard)/controls/page.tsx` (`Section`, and its "Danger zone" call site)
- Test: `web/app/(dashboard)/controls/page.test.tsx`

**Finding:** The `<Section title="Danger zone">` header uses the same `text-sm font-semibold text-ink` styling as every other collapsed section header ("Chrome Extension", etc.) before the user expands it — no signal of severity while collapsed.

**Investigated (per plan caveat):** `DESIGN.md:462` forbids side-stripe colored accents ("Don't use side-stripe borders as colored accents. Use full borders, labeled badges, or background tints instead.") but says nothing against a plain text-color cue. `text-status-error` (`#f87171`) is already used throughout this file for destructive text (the delete button, error messages), so applying it to just the "Danger zone" title text is consistent with existing usage and doesn't violate the side-stripe rule (it's neither a stripe nor decorative — it's the same semantic color already meaning "destructive" everywhere else on this page).

- [ ] **Step 1: Write the failing test**

Add to `web/app/(dashboard)/controls/page.test.tsx`:

```tsx
it('gives the Danger zone section title a distinct text treatment', () => {
  render(<ControlsPage />);
  const title = screen.getByText('Danger zone');
  expect(title.className).toContain('text-status-error');

  const otherTitle = screen.getByText('Chrome Extension');
  expect(otherTitle.className).not.toContain('text-status-error');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: FAIL — "Danger zone" currently renders as plain text with no wrapping element carrying `text-status-error`.

- [ ] **Step 3: Add an optional `titleClassName` prop to `Section`**

In `web/app/(dashboard)/controls/page.tsx`, change the `Section` component:

```tsx
function Section({
  title,
  titleClassName,
  defaultOpen,
  children,
}: {
  title: string;
  titleClassName?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDetailsElement>(null);
  const reducedMotion = useReducedMotion();

  return (
    <details
      ref={ref}
      open={defaultOpen}
      onToggle={() => {
        ref.current?.scrollIntoView?.({
          behavior: reducedMotion ? 'auto' : 'smooth',
          block: 'nearest',
        });
      }}
      className="group overflow-hidden rounded-lg border border-line bg-surface"
    >
      <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-semibold text-ink transition-ui hover:bg-raised [&::-webkit-details-marker]:hidden">
        <span className={titleClassName}>{title}</span>
        <OwnixChevronDown className="h-4 w-4 text-muted transition-transform group-open:rotate-180" />
      </summary>
      <div className="border-t border-line bg-canvas p-4">
        {children}
      </div>
    </details>
  );
}
```

(`titleClassName` is `undefined` for every other `<Section>` call site, so the wrapping `<span>` there carries no class — no visual change for them.)

Then, in `export default function ControlsPage()`, change the "Danger zone" call site:

```tsx
        <Section
          title="Danger zone"
          titleClassName="text-status-error"
        >
          <DeleteAccountSection />
        </Section>
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `web/`): `npm run test:run -- page.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run the full frontend suite for regressions**

Run (from `web/`): `npm run test:run`
Expected: all pass — confirm the other `<Section>` call sites ("Tags", "Domains", "Chrome Extension") render identically to before (no `titleClassName` passed).

- [ ] **Step 6: Run lint**

Run (from `web/`): `npm run lint`
Expected: no new lint errors.

- [ ] **Step 7: Commit**

```bash
git add web/app/\(dashboard\)/controls/page.tsx web/app/\(dashboard\)/controls/page.test.tsx
git commit -m "style(controls): give the Danger zone section title a destructive text treatment"
```

---

## Final verification

After all 15 tasks are committed:

- [ ] Run the full scoped backend suite once more: `python -m pytest tests/test_auth.py tests/test_account.py tests/test_database.py -q --timeout=60` (PowerShell) — expect all pass.
- [ ] Run the full backend suite for a final regression check: `python -m pytest tests -q --timeout=60` (PowerShell) — expect only the pre-existing ~15-27 unrelated baseline failures noted in project memory, none newly introduced by this plan.
- [ ] Run `ruff check src/` — expect no new lint errors in `src/database.py`, `src/api/auth.py`, `src/services/account.py`.
- [ ] Run the full frontend suite: `npm run test:run` (from `web/`) — expect all pass.
- [ ] Run `npm run lint` (from `web/`) — expect no new lint errors.
