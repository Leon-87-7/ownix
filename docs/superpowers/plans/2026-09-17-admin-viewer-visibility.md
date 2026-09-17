# Admin/Viewer Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the operator full access plus a way to see exactly what an invitee sees, hide Newsletter Digest from non-admins at both the nav and the API layer, fix Recipes so it ships as a real feature for everyone, and give the operator an early warning when Gemini starts failing.

**Architecture:** No new `role` column — the codebase already has a single-operator admin concept (`settings.OPERATOR_CHAT_ID`, already special-cased in `database.get_user_status`/`set_user_status`). This plan adds a `Settings.is_operator()` helper and reuses it everywhere "admin" needs to be checked. The "viewer" backdoor is one real, synthetic `users` row (mirroring the existing Chrome-reviewer login pattern in `src/api/auth.py`) reachable two ways: its own email+password login (for a side-by-side incognito session), or a same-tab toggle that swaps the admin's *effective* acting identity to that same row via a short-lived cookie read in `SessionMiddleware`. Because both paths land on the same row, it starts empty and accumulates real jobs as it's used. Newsletter Digest is gated by the same `is_operator()` check, applied after any toggle substitution, at both the Next.js nav layer and the FastAPI route layer (404, not 403 — a hidden route shouldn't confirm its own existence). Recipes' fix is unrelated to any of this — it's `src/api/jobs.py`'s `_resolve_job_template` not knowing how to look up a saved template by name, and ships open to every role once fixed. The Gemini alert reuses the ops bot's existing admin-notification channel (`src/services/ops_bot.py`), not new infrastructure.

**Tech Stack:** FastAPI + aiosqlite (backend), Next.js 16 App Router + React 19 (frontend), pytest (backend tests), Vitest + RTL (frontend tests).

**Spec:** This plan's spec is the conversation that produced it — no separate spec doc. Key decisions, verbatim from that conversation:
- Admin (the operator) always sees every feature, no exceptions.
- A same-session "view as member" toggle exists for quick empty-state checks, and a separate literal viewer login exists for side-by-side testing — both point at the same underlying account so it never drifts and can accumulate real submitted jobs.
- Docs (PDF/document parsing) stays visible to everyone — it's a core builder capability, not row-two.
- Recipes is not hidden-by-default; its broken apply-path gets fixed, then it ships visible for every role.
- Newsletter Digest is the only feature hidden from non-admins for now.
- The Gemini failure-rate alert reuses the existing ops-bot admin Telegram channel rather than adding new monitoring infrastructure.

## Global Constraints

- Python: `ruff check src/` must pass (line-length 100, py311). No new lint violations.
- Backend tests run via `python -m pytest tests -q` (never through `rtk` — see `.claude/rules/rtk-tests.md`); run via **PowerShell**, not Bash (project convention — Bash silently hangs pytest here).
- Frontend tests run via `npm test` / `npm run test:run` under `web/`; run via **PowerShell**, not Bash, same reason.
- No em dashes, no fabricated claims, no new dependencies for anything this plan can do with what's already installed (FastAPI, aiosqlite, Next.js, lucide-react are all already in the project).
- Follow existing patterns exactly: session cookies via `response.set_cookie(...secure=settings.SESSION_COOKIE_SECURE, samesite="lax"...)`, `database.*` facade re-exports (never import `src/db/*.py` submodules directly from API/service code), `'use client'` + `usePathname`/`useRouter` for interactive nav.
- `Settings.OPERATOR_CHAT_ID` may be `None` (no operator configured) — every new admin check must treat that as "no one is admin," never as "everyone is admin."

---

## Task 1: `Settings.is_operator()` + viewer-login/view-as settings

**Files:**
- Modify: `src/config.py` (add a method near `export_blocked`, add new settings near `REVIEWER_LOGIN_*`)
- Test: `tests/test_config.py` (create if it doesn't already cover `Settings` directly — check first; if a general settings test file exists, add to it instead)

**Interfaces:**
- Produces: `Settings.is_operator(chat_id: int | None) -> bool`; new settings `VIEWER_LOGIN_ENABLED: bool`, `VIEWER_LOGIN_EMAIL: str`, `VIEWER_LOGIN_PASSWORD: str`, `VIEWER_LOGIN_USER_ID: int`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from src.config import Settings


def test_is_operator_true_for_matching_chat_id():
    s = Settings(OPERATOR_CHAT_ID=123456789)
    assert s.is_operator(123456789) is True


def test_is_operator_false_for_other_chat_id():
    s = Settings(OPERATOR_CHAT_ID=123456789)
    assert s.is_operator(987654321) is False


def test_is_operator_false_when_unconfigured():
    s = Settings(OPERATOR_CHAT_ID=None)
    assert s.is_operator(123456789) is False


def test_is_operator_false_for_none_chat_id():
    s = Settings(OPERATOR_CHAT_ID=123456789)
    assert s.is_operator(None) is False
```

If `tests/test_config.py` doesn't exist yet, create it with this content plus `from __future__ import annotations` at the top (match every other file in `src/`).

- [ ] **Step 2: Run test to verify it fails**

Run (PowerShell): `python -m pytest tests/test_config.py -v`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'is_operator'`

- [ ] **Step 3: Write minimal implementation**

In `src/config.py`, add the method next to `export_blocked` (same class, same section):

```python
    def is_operator(self, chat_id: int | None) -> bool:
        """True only when OPERATOR_CHAT_ID is configured and matches chat_id.

        Drives every "admin sees everything" / "hide this from non-admins"
        check in the app — deliberately the same OPERATOR_CHAT_ID this class
        already special-cases in database.get_user_status/set_user_status,
        not a new role concept.
        """
        return self.OPERATOR_CHAT_ID is not None and chat_id == self.OPERATOR_CHAT_ID
```

And add the new settings immediately after the existing `REVIEWER_LOGIN_*` block:

```python
    # Admin-only "view as a member" backdoor — a synthetic member account
    # (not a role system) so the operator can see an empty, real invitee
    # experience and submit real jobs against it. Keep disabled except when
    # actually needed; rotate VIEWER_LOGIN_PASSWORD if it's ever enabled.
    VIEWER_LOGIN_ENABLED: bool = False
    VIEWER_LOGIN_EMAIL: str = ""
    VIEWER_LOGIN_PASSWORD: str = ""
    VIEWER_LOGIN_USER_ID: int = -900_000_002
```

- [ ] **Step 4: Run test to verify it passes**

Run (PowerShell): `python -m pytest tests/test_config.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat(config): add Settings.is_operator() and viewer-login settings"
```

---

## Task 2: Viewer login endpoint

**Files:**
- Modify: `src/api/auth.py` (add `ViewerLoginPayload` + `viewer_login` route, near `reviewer_login`)
- Modify: `src/auth/middleware.py` (add `/api/auth/viewer-login` to `_OPEN_API_PATHS`)
- Test: `tests/test_auth.py` (add to the existing `auth_client`-based test class)

**Interfaces:**
- Consumes: `Settings.is_operator` not needed here (this route is reachable by anyone with the password, same as reviewer-login — the *toggle* in Task 3 is the admin-gated path). Consumes existing `database.upsert_user`, `database.set_user_email`, `database.set_user_status`, `session_store.mint`, `rate_limit.enforce`, `normalize_email`, `_resume_deletion_if_stuck` — all already imported in `src/api/auth.py`.
- Produces: `POST /api/auth/viewer-login` — same response shape as `POST /api/auth/reviewer-login` (`{"ok": True}` + `vig_session` cookie set).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_auth.py`, in the same test class/section as the existing `test_reviewer_login_*` tests (search for `class TestSessionMiddleware` or the reviewer-login tests' surrounding class and place these alongside them):

```python
    def test_viewer_login_is_disabled_by_default(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.api.auth.settings.VIEWER_LOGIN_ENABLED", False)

        resp = auth_client.post(
            "/api/auth/viewer-login",
            json={"email": "viewer@example.com", "password": "viewer-code"},
        )

        assert resp.status_code == 404
        assert "vig_session=" not in resp.headers.get("set-cookie", "")

    def test_viewer_login_rejects_invalid_credentials(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.api.auth.settings.VIEWER_LOGIN_ENABLED", True)
        monkeypatch.setattr("src.api.auth.settings.VIEWER_LOGIN_EMAIL", "viewer@example.com")
        monkeypatch.setattr("src.api.auth.settings.VIEWER_LOGIN_PASSWORD", "viewer-code")

        resp = auth_client.post(
            "/api/auth/viewer-login",
            json={"email": "viewer@example.com", "password": "wrong"},
        )

        assert resp.status_code == 401
        assert "vig_session=" not in resp.headers.get("set-cookie", "")

    def test_viewer_login_succeeds_and_creates_approved_member(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.api.auth.settings.VIEWER_LOGIN_ENABLED", True)
        monkeypatch.setattr("src.api.auth.settings.VIEWER_LOGIN_EMAIL", "viewer@example.com")
        monkeypatch.setattr("src.api.auth.settings.VIEWER_LOGIN_PASSWORD", "viewer-code")
        monkeypatch.setattr("src.api.auth.settings.VIEWER_LOGIN_USER_ID", -900_000_002)

        resp = auth_client.post(
            "/api/auth/viewer-login",
            json={"email": "viewer@example.com", "password": "viewer-code"},
        )

        assert resp.status_code == 200
        assert "vig_session=" in resp.headers.get("set-cookie", "")

        from src import database
        import asyncio

        status = asyncio.run(database.get_user_status(-900_000_002))
        assert status == "approved"
```

- [ ] **Step 2: Run test to verify it fails**

Run (PowerShell): `python -m pytest tests/test_auth.py -k viewer_login -v`
Expected: FAIL — all three with 404 "Not Found" (route doesn't exist yet), since FastAPI returns 404 for an unmatched route too; the `test_viewer_login_is_disabled_by_default` test will misleadingly "pass" on status code alone — confirm the other two genuinely fail on `set-cookie`/behavior, or temporarily assert `resp.json()["detail"] != "Not Found"` is false to be sure. Simpler: run `test_viewer_login_succeeds_and_creates_approved_member` alone first — it must fail with a 404 whose body is FastAPI's default "Not Found" (no `vig_session` cookie), confirming the route is genuinely missing before Step 3.

- [ ] **Step 3: Write minimal implementation**

In `src/api/auth.py`, add directly after the existing `reviewer_login` function:

```python
class ViewerLoginPayload(BaseModel):
    email: str = Field(..., max_length=254)
    password: str = Field(..., max_length=256)


@auth_router.post("/viewer-login")
async def viewer_login(payload: ViewerLoginPayload, response: Response) -> dict:
    """Admin-configured synthetic member account — lets the operator see the
    app exactly as an invitee would (starts empty, can submit real jobs).

    Not a general auth provider, same as reviewer_login above. Disabled by
    default; the same session_id/cookie this route mints is also what the
    view-as toggle (Task 3) substitutes into an admin's own session.
    """
    configured_email = normalize_email(settings.VIEWER_LOGIN_EMAIL)
    submitted_email = normalize_email(payload.email)
    configured_password = settings.VIEWER_LOGIN_PASSWORD
    submitted_password = payload.password.strip()
    if not (settings.VIEWER_LOGIN_ENABLED and configured_email and configured_password):
        raise HTTPException(status_code=404, detail="Viewer login is disabled")
    rate_limit.enforce(f"viewer_login:{submitted_email}", max_requests=5)
    if submitted_email != configured_email or not hmac.compare_digest(
        submitted_password.encode("utf-8"),
        configured_password.encode("utf-8"),
    ):
        raise HTTPException(status_code=401, detail="Invalid viewer credentials")

    viewer_id = settings.VIEWER_LOGIN_USER_ID
    resumed = await _resume_deletion_if_stuck(viewer_id)
    if resumed is not None:
        return resumed

    await database.upsert_user(
        tg_id=viewer_id,
        username="ownix_viewer",
        first_name="Viewer",
        last_name=None,
        photo_url=None,
    )
    await database.set_user_email(viewer_id, configured_email)
    await database.set_user_status(viewer_id, "approved")
    session_id = await session_store.mint(
        {
            "id": viewer_id,
            "first_name": "Viewer",
            "username": "ownix_viewer",
            "source": "viewer_login",
        }
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )
    log.info("auth.viewer_login", tg_id=viewer_id)
    return {"ok": True}
```

In `src/auth/middleware.py`, add `"/api/auth/viewer-login"` to `_OPEN_API_PATHS` (it's a frozenset literal — add the new string as another element, alphabetically near `"/api/auth/reviewer-login"`).

- [ ] **Step 4: Run test to verify it passes**

Run (PowerShell): `python -m pytest tests/test_auth.py -k viewer_login -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/api/auth.py src/auth/middleware.py tests/test_auth.py
git commit -m "feat(auth): add admin-only viewer-login endpoint"
```

---

## Task 3: View-as toggle (middleware substitution + endpoints)

**Files:**
- Modify: `src/auth/middleware.py` (define `VIEW_AS_COOKIE`, attach `real_id`, substitute `id` when toggled)
- Modify: `src/api/auth.py` (add `POST /api/auth/view-as` and `DELETE /api/auth/view-as`)
- Test: `tests/test_auth.py`

**Interfaces:**
- Consumes: `Settings.is_operator` (Task 1), `Settings.VIEWER_LOGIN_ENABLED`/`VIEWER_LOGIN_USER_ID` (Task 1).
- Produces: `request.state.user` always carries `real_id: int`; carries `id == settings.VIEWER_LOGIN_USER_ID` instead of the real id whenever the `ownix_view_as` cookie is set on an operator's session. `POST /api/auth/view-as` (204, sets the cookie), `DELETE /api/auth/view-as` (204, clears it) — both 403 for a non-operator `real_id`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_auth.py`, same class as Task 2's tests:

```python
    def test_view_as_toggle_requires_operator(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", 999)
        monkeypatch.setattr("src.auth.middleware.settings.OPERATOR_CHAT_ID", 999)

        auth_client.cookies.set("vig_session", "fixed-session-id")
        import src.auth.session as session_module

        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:fixed-session-id"] = '{"id": 111, "first_name": "Not Admin"}'

        from src import database
        import asyncio

        asyncio.run(database.set_user_status(111, "approved"))

        resp = auth_client.post("/api/auth/view-as")
        assert resp.status_code == 403

    def test_view_as_toggle_substitutes_effective_id(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", 999)
        monkeypatch.setattr("src.auth.middleware.settings.OPERATOR_CHAT_ID", 999)
        monkeypatch.setattr("src.api.auth.settings.VIEWER_LOGIN_ENABLED", True)
        monkeypatch.setattr("src.api.auth.settings.VIEWER_LOGIN_USER_ID", -900_000_002)
        monkeypatch.setattr("src.auth.middleware.settings.VIEWER_LOGIN_USER_ID", -900_000_002)

        auth_client.cookies.set("vig_session", "fixed-session-id")
        import src.auth.session as session_module

        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:fixed-session-id"] = '{"id": 999, "first_name": "Operator"}'

        from src import database
        import asyncio

        asyncio.run(database.set_user_status(999, "approved"))
        asyncio.run(database.set_user_status(-900_000_002, "approved"))

        toggle_on = auth_client.post("/api/auth/view-as")
        assert toggle_on.status_code == 204

        probe = auth_client.get("/api/probe")
        assert probe.json()["user"]["id"] == -900_000_002
        assert probe.json()["user"]["real_id"] == 999

        toggle_off = auth_client.delete("/api/auth/view-as")
        assert toggle_off.status_code == 204

        probe_after = auth_client.get("/api/probe")
        assert probe_after.json()["user"]["id"] == 999
```

- [ ] **Step 2: Run test to verify it fails**

Run (PowerShell): `python -m pytest tests/test_auth.py -k view_as -v`
Expected: FAIL — `POST /api/auth/view-as` returns 404 (route doesn't exist), and `request.state.user` has no `real_id` key.

- [ ] **Step 3: Write minimal implementation**

In `src/auth/middleware.py`, add the cookie constant near `COOKIE_NAME`:

```python
COOKIE_NAME = "vig_session"
VIEW_AS_COOKIE = "ownix_view_as"
```

Replace the tail of `dispatch` (from `request.state.user = user` through the final `return await call_next(request)`) with:

```python
        real_id = int(user["id"])
        effective_user = dict(user)
        effective_user["real_id"] = real_id
        if settings.is_operator(real_id) and request.cookies.get(VIEW_AS_COOKIE) == "1":
            effective_user["id"] = settings.VIEWER_LOGIN_USER_ID
        request.state.user = effective_user

        # Only these auth routes are intentionally reachable before approval.
        if path in _PRE_APPROVAL_AUTH_PATHS:
            return await call_next(request)

        status = await database.get_user_status(int(request.state.user["id"]))
        if status != "approved":
            return JSONResponse({"detail": "Approval required"}, status_code=403)

        if path.startswith("/api/newsletter") and not settings.is_operator(
            int(request.state.user["id"])
        ):
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        return await call_next(request)
```

(The `path.startswith("/api/newsletter")` block belongs to Task 5, but it's included here since it's a one-line addition to the same code block Task 3 already rewrites — Task 5 will only need its own test, not another middleware edit.)

In `src/api/auth.py`, add directly after the new `viewer_login` route:

```python
@auth_router.post("/view-as", status_code=204)
async def enter_view_as(request: Request, response: Response) -> None:
    """Admin-only: start rendering this session as the viewer account."""
    real_id = int(request.state.user.get("real_id", request.state.user["id"]))
    if not settings.is_operator(real_id):
        raise HTTPException(status_code=403, detail="Admin only")
    if not settings.VIEWER_LOGIN_ENABLED:
        raise HTTPException(status_code=404, detail="Viewer account not configured")
    response.set_cookie(
        key="ownix_view_as",
        value="1",
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


@auth_router.delete("/view-as", status_code=204)
async def exit_view_as(request: Request, response: Response) -> None:
    """Admin-only: stop rendering this session as the viewer account."""
    real_id = int(request.state.user.get("real_id", request.state.user["id"]))
    if not settings.is_operator(real_id):
        raise HTTPException(status_code=403, detail="Admin only")
    response.delete_cookie("ownix_view_as", path="/", secure=settings.SESSION_COOKIE_SECURE)
```

Both routes are ordinary authenticated routes (not in `_OPEN_API_PATHS`), so `request.state.user` is already populated by the middleware by the time they run — no new import needed beyond what `src/api/auth.py` already has.

- [ ] **Step 4: Run test to verify it passes**

Run (PowerShell): `python -m pytest tests/test_auth.py -k "view_as or viewer_login" -v`
Expected: PASS (5 tests total across Task 2 and Task 3)

- [ ] **Step 5: Commit**

```bash
git add src/auth/middleware.py src/api/auth.py tests/test_auth.py
git commit -m "feat(auth): add admin-only view-as toggle"
```

---

## Task 4: Expose admin/viewing-as state on `/me` + frontend toggle

**Files:**
- Modify: `src/api/auth.py` (extend the `me()` response)
- Modify: `web/components/shell/invite-gate.tsx` (extend `InviteUser` type)
- Create: `web/components/shell/view-as-switch.tsx`
- Modify: `web/app/(dashboard)/layout.tsx` (render the switch, same placement tier as `DevPersonaSwitch`)
- Test: `tests/test_auth.py` (backend), `web/components/shell/view-as-switch.test.tsx` (frontend)

**Interfaces:**
- Produces: `GET /api/auth/me` response gains `is_admin: bool`, `can_view_as: bool`, `viewing_as: bool`. `InviteUser` (frontend) gains the same three fields, all optional (`?:`) so existing call sites compile untouched.

- [ ] **Step 1: Write the failing backend test**

Add to `tests/test_auth.py`:

```python
    def test_me_reports_admin_and_viewing_as_flags(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", 999)
        monkeypatch.setattr("src.auth.middleware.settings.OPERATOR_CHAT_ID", 999)
        monkeypatch.setattr("src.api.auth.settings.OPERATOR_CHAT_ID", 999)
        monkeypatch.setattr("src.api.auth.settings.VIEWER_LOGIN_ENABLED", True)
        monkeypatch.setattr("src.api.auth.settings.VIEWER_LOGIN_USER_ID", -900_000_002)
        monkeypatch.setattr("src.auth.middleware.settings.VIEWER_LOGIN_USER_ID", -900_000_002)

        auth_client.cookies.set("vig_session", "fixed-session-id")
        import src.auth.session as session_module

        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:fixed-session-id"] = '{"id": 999, "first_name": "Operator"}'

        from src import database
        import asyncio

        asyncio.run(database.set_user_status(999, "approved"))
        asyncio.run(database.set_user_status(-900_000_002, "approved"))

        me_before = auth_client.get("/api/auth/me")
        assert me_before.json()["is_admin"] is True
        assert me_before.json()["viewing_as"] is False
        assert me_before.json()["can_view_as"] is True

        auth_client.post("/api/auth/view-as")
        me_after = auth_client.get("/api/auth/me")
        assert me_after.json()["is_admin"] is False
        assert me_after.json()["viewing_as"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run (PowerShell): `python -m pytest tests/test_auth.py -k reports_admin -v`
Expected: FAIL — `KeyError: 'is_admin'`

- [ ] **Step 3: Write minimal backend implementation**

In `src/api/auth.py`, replace the `return {...}` body of `me()`:

```python
    tg_id = int(session_user["id"])
    real_id = int(session_user.get("real_id", tg_id))
    return {
        **session_user,
        "email": db_user.get("email") if db_user else None,
        "status": status,
        "is_admin": settings.is_operator(tg_id),
        "can_view_as": settings.is_operator(real_id) and settings.VIEWER_LOGIN_ENABLED,
        "viewing_as": real_id != tg_id,
    }
```

(`tg_id` is already computed at the top of `me()` — only the `real_id` line and the three new dict keys are new.)

- [ ] **Step 4: Run test to verify it passes**

Run (PowerShell): `python -m pytest tests/test_auth.py -k reports_admin -v`
Expected: PASS

- [ ] **Step 5: Extend the frontend type**

In `web/components/shell/invite-gate.tsx`, extend `InviteUser`:

```typescript
export interface InviteUser {
  id: number;
  first_name?: string;
  username?: string | null;
  photo_url?: string | null;
  email?: string | null;
  status: UserStatus;
  is_admin?: boolean;
  can_view_as?: boolean;
  viewing_as?: boolean;
}
```

- [ ] **Step 6: Write the failing frontend test**

Create `web/components/shell/view-as-switch.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ViewAsSwitch } from './view-as-switch';
import * as inviteGate from './invite-gate';

vi.mock('./invite-gate', async () => {
  const actual = await vi.importActual<typeof inviteGate>('./invite-gate');
  return { ...actual, useSessionUser: vi.fn() };
});

describe('ViewAsSwitch', () => {
  beforeEach(() => {
    vi.mocked(inviteGate.useSessionUser).mockReset();
    global.fetch = vi.fn();
  });

  it('renders nothing for a user who cannot view-as and is not currently viewing as', () => {
    vi.mocked(inviteGate.useSessionUser).mockReturnValue({
      id: 1,
      status: 'approved',
      is_admin: false,
      can_view_as: false,
      viewing_as: false,
    });
    const { container } = render(<ViewAsSwitch />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows "View as member" for an admin who can view-as', () => {
    vi.mocked(inviteGate.useSessionUser).mockReturnValue({
      id: 999,
      status: 'approved',
      is_admin: true,
      can_view_as: true,
      viewing_as: false,
    });
    render(<ViewAsSwitch />);
    expect(screen.getByRole('button', { name: /view as member/i })).toBeInTheDocument();
  });

  it('shows "Exit viewer mode" while viewing as the member account, and posts DELETE on click', async () => {
    vi.mocked(inviteGate.useSessionUser).mockReturnValue({
      id: -900000002,
      status: 'approved',
      is_admin: false,
      can_view_as: true,
      viewing_as: true,
    });
    vi.mocked(global.fetch).mockResolvedValue({ ok: true } as Response);
    const reloadSpy = vi.fn();
    vi.stubGlobal('location', { ...window.location, reload: reloadSpy });

    render(<ViewAsSwitch />);
    fireEvent.click(screen.getByRole('button', { name: /exit viewer mode/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/auth/view-as', { method: 'DELETE' });
    });
  });
});
```

- [ ] **Step 7: Run test to verify it fails**

Run (PowerShell, from `web/`): `npm run test:run -- view-as-switch`
Expected: FAIL — `Cannot find module './view-as-switch'`

- [ ] **Step 8: Write minimal frontend implementation**

Create `web/components/shell/view-as-switch.tsx`:

```typescript
'use client';

import { useSessionUser } from './invite-gate';

// Admin-only. Mirrors DevPersonaSwitch's placement (outside InviteGate, in
// the dashboard layout) but gated on the real session's is_admin/viewing_as
// fields instead of a mock-build env flag, since this must work in real
// production for the operator.
export function ViewAsSwitch() {
  const user = useSessionUser();
  if (!user) return null;
  if (!user.is_admin && !user.viewing_as) return null;

  const enter = async () => {
    await fetch('/api/auth/view-as', { method: 'POST' });
    window.location.reload();
  };
  const exit = async () => {
    await fetch('/api/auth/view-as', { method: 'DELETE' });
    window.location.reload();
  };

  if (user.viewing_as) {
    return (
      <button
        type="button"
        onClick={exit}
        className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 rounded-full border border-signal bg-canvas px-4 py-2 text-button font-medium text-signal shadow-overlay transition-ui hover:bg-raised"
      >
        Viewing as member — Exit viewer mode
      </button>
    );
  }
  if (user.can_view_as) {
    return (
      <button
        type="button"
        onClick={enter}
        className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 rounded-full border border-line bg-surface px-4 py-2 text-button font-medium text-body shadow-overlay transition-ui hover:bg-raised hover:text-ink"
      >
        View as member
      </button>
    );
  }
  return null;
}
```

- [ ] **Step 9: Run test to verify it passes**

Run (PowerShell, from `web/`): `npm run test:run -- view-as-switch`
Expected: PASS (3 tests)

- [ ] **Step 10: Render it in the dashboard layout**

In `web/app/(dashboard)/layout.tsx`, add the import and render it next to `DevPersonaSwitch`:

```typescript
import DevPersonaSwitch from '@/components/ui/dev-persona-switch';
import { ViewAsSwitch } from '@/components/shell/view-as-switch';
```

```jsx
        {/* Outside InviteGate so the dev switch survives the gate screen. */}
        <DevPersonaSwitch />
        <ViewAsSwitch />
        <ToastHost />
```

- [ ] **Step 11: Commit**

```bash
git add src/api/auth.py web/components/shell/invite-gate.tsx web/components/shell/view-as-switch.tsx web/components/shell/view-as-switch.test.tsx "web/app/(dashboard)/layout.tsx" tests/test_auth.py
git commit -m "feat(auth): surface admin/viewing-as state and add the view-as switch"
```

---

## Task 5: Backend gate for Newsletter Digest (test only — the gate itself landed in Task 3)

**Files:**
- Test: `tests/test_auth.py` (or a newsletter-digest-specific test file if one already exists — check `tests/test_api_newsletter_digest.py` first and add there if so)

**Interfaces:**
- Consumes: the `path.startswith("/api/newsletter")` block added in Task 3's `middleware.py` edit.

- [ ] **Step 1: Write the failing test**

If `tests/test_api_newsletter_digest.py` exists, add this test there (adjust the fixture name to whatever that file's existing FastAPI test client fixture is called); otherwise add to `tests/test_auth.py`'s `auth_client`-based class, first adding a stub `/api/newsletter/probe` route to the `auth_client` fixture's `test_app` (mirroring how `/api/probe` and `/api/google/connect` are already stubbed there):

```python
    def test_newsletter_routes_404_for_non_admin(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", 999)
        monkeypatch.setattr("src.auth.middleware.settings.OPERATOR_CHAT_ID", 999)

        auth_client.cookies.set("vig_session", "fixed-session-id")
        import src.auth.session as session_module

        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:fixed-session-id"] = '{"id": 111, "first_name": "Member"}'

        from src import database
        import asyncio

        asyncio.run(database.set_user_status(111, "approved"))

        resp = auth_client.get("/api/newsletter/probe")
        assert resp.status_code == 404

    def test_newsletter_routes_reachable_for_admin(
        self, auth_client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("src.config.settings.OPERATOR_CHAT_ID", 999)
        monkeypatch.setattr("src.auth.middleware.settings.OPERATOR_CHAT_ID", 999)

        auth_client.cookies.set("vig_session", "fixed-session-id")
        import src.auth.session as session_module

        fr: FakeRedis = session_module._redis  # type: ignore[assignment]
        fr._store["session:fixed-session-id"] = '{"id": 999, "first_name": "Operator"}'

        from src import database
        import asyncio

        asyncio.run(database.set_user_status(999, "approved"))

        resp = auth_client.get("/api/newsletter/probe")
        assert resp.status_code == 200
```

Add the stub route to the `auth_client` fixture in `tests/test_auth.py`, alongside the existing `/api/probe` stub:

```python
    @test_app.get("/api/newsletter/probe")
    async def newsletter_probe(request: Request) -> dict:
        return {"user": request.state.user}
```

- [ ] **Step 2: Run test to verify it fails**

Run (PowerShell): `python -m pytest tests/test_auth.py -k newsletter_routes -v`
Expected: If Task 3 was completed as written, this actually PASSES already (the gate was added there). Run it to confirm — if it fails, the Task 3 edit was incomplete; fix `src/auth/middleware.py` before continuing.

- [ ] **Step 3: N/A — implementation already landed in Task 3**

- [ ] **Step 4: Run test to verify it passes**

Run (PowerShell): `python -m pytest tests/test_auth.py -k newsletter_routes -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add tests/test_auth.py
git commit -m "test(auth): cover the newsletter-digest admin gate"
```

---

## Task 6: Frontend nav filter + page guard for Newsletter Digest

**Files:**
- Modify: `web/components/shell/sidebar.tsx`
- Modify: `web/app/(dashboard)/newsletter-digest/page.tsx`
- Test: `web/components/shell/sidebar.test.tsx` (add to existing file)

**Interfaces:**
- Consumes: `useSessionUser().is_admin` (Task 4).

- [ ] **Step 1: Write the failing test**

Check `web/components/shell/sidebar.test.tsx` first for its existing mock pattern for `useSessionUser` (it almost certainly already mocks `./invite-gate` for other tests — reuse that exact mock setup). Add:

```typescript
  it('hides the Digest nav item for a non-admin user', () => {
    vi.mocked(inviteGate.useSessionUser).mockReturnValue({
      id: 111,
      status: 'approved',
      is_admin: false,
    });
    render(<Sidebar />);
    expect(screen.queryByRole('link', { name: /digest/i })).not.toBeInTheDocument();
  });

  it('shows the Digest nav item for an admin user', () => {
    vi.mocked(inviteGate.useSessionUser).mockReturnValue({
      id: 999,
      status: 'approved',
      is_admin: true,
    });
    render(<Sidebar />);
    expect(screen.getAllByRole('link', { name: /digest/i }).length).toBeGreaterThan(0);
  });
```

(Adjust the import alias for `inviteGate` and the mock declaration to match whatever `sidebar.test.tsx` already uses for other `useSessionUser`-dependent tests in that file — don't introduce a second, differently-shaped mock.)

- [ ] **Step 2: Run test to verify it fails**

Run (PowerShell, from `web/`): `npm run test:run -- sidebar`
Expected: FAIL — both tests find the Digest link regardless of `is_admin` (nav isn't filtered yet).

- [ ] **Step 3: Write minimal implementation**

In `web/components/shell/sidebar.tsx`, the `NAV` constant stays as the full list (single source of truth for hrefs/icons), but add a helper and use it in both render sites:

```typescript
const NAV: NavItem[] = [
  { href: '/intake', label: 'Intake', icon: Inbox },
  { href: '/feed', label: 'Feed', icon: Rss },
  { href: '/newsletter-digest', label: 'Digest', icon: Newspaper },
  { href: '/doc-parser', label: 'Docs', icon: FileCode2 },
  { href: '/brain', label: 'Brain', icon: Brain },
  { href: '/spaces', label: 'Collections', icon: LayoutGrid },
  { href: '/prompts', label: 'Recipes', icon: MessageSquareText },
  { href: '/controls', label: 'Settings', icon: SlidersHorizontal },
];

// Newsletter Digest is the only nav item gated on admin — see
// docs/superpowers/plans/2026-09-17-admin-viewer-visibility.md. The API
// route is gated server-side too (src/auth/middleware.py); this hides the
// link, the middleware makes the URL itself 404 for non-admins.
const ADMIN_ONLY_HREFS = new Set(['/newsletter-digest']);

function visibleNav(isAdmin: boolean): NavItem[] {
  return isAdmin ? NAV : NAV.filter((item) => !ADMIN_ONLY_HREFS.has(item.href));
}
```

Inside `export function Sidebar()`, right after `const user = useSessionUser();`:

```typescript
  const nav = visibleNav(Boolean(user?.is_admin));
```

Then replace both `{NAV.map((item) => (` occurrences (collapsed rail and expanded drawer) with `{nav.map((item) => (`.

- [ ] **Step 4: Run test to verify it passes**

Run (PowerShell, from `web/`): `npm run test:run -- sidebar`
Expected: PASS

- [ ] **Step 5: Add the page-level guard (defense in depth)**

In `web/app/(dashboard)/newsletter-digest/page.tsx`, add a client-side redirect for a non-admin who reaches the URL directly (the API itself already 404s any data fetch, so this is a friendlier UX guard, not the security boundary):

Read the top of that file first to match its existing imports/structure, then add near the top of the page component body:

```typescript
  const user = useSessionUser();
  const router = useRouter();
  useEffect(() => {
    if (user && !user.is_admin) {
      router.replace('/feed');
    }
  }, [user, router]);
  if (user && !user.is_admin) return null;
```

(Import `useSessionUser` from `@/components/shell/invite-gate`, `useRouter` from `next/navigation`, and `useEffect` from `react` — add whichever of these three imports the file doesn't already have.)

- [ ] **Step 6: Commit**

```bash
git add web/components/shell/sidebar.tsx web/components/shell/sidebar.test.tsx "web/app/(dashboard)/newsletter-digest/page.tsx"
git commit -m "feat(nav): hide Newsletter Digest from non-admin users"
```

---

## Task 7: Recipes — `_resolve_job_template` resolves saved recipes

**Files:**
- Modify: `src/api/jobs.py`
- Test: `tests/test_api_jobs.py` (check this file exists first via `find tests -iname "*jobs*"`; if the jobs API has a differently-named test file, use that one instead)

**Interfaces:**
- Consumes: `database.get_user_template_by_name(chat_id: int, name: str) -> dict | None` (already exists, already re-exported on `database`).
- Produces: `_resolve_job_template` becomes `async def _resolve_job_template(chat_id: int, pipeline: str, template: str | None, freestyle_prompt: str | None) -> tuple[str | None, str | None]` — a `template` that names neither a built-in nor `"freestyle"` is now looked up as a saved recipe; if found, resolves to `("freestyle", <recipe's extra_instructions>)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api_jobs.py (append; adjust imports/fixtures to match the file's existing style)
import pytest

from src.api.jobs import _resolve_job_template


@pytest.mark.asyncio
async def test_resolve_job_template_passes_through_builtin():
    template, freestyle_prompt = await _resolve_job_template(123, "long", "summary", None)
    assert template == "summary"
    assert freestyle_prompt is None


@pytest.mark.asyncio
async def test_resolve_job_template_resolves_saved_recipe_to_freestyle(monkeypatch):
    from src import database

    await database.create_user_template(
        chat_id=123,
        name="my-recipe",
        description="test recipe",
        extra_instructions="Summarize as a bulleted checklist.",
    )

    template, freestyle_prompt = await _resolve_job_template(123, "long", "my-recipe", None)

    assert template == "freestyle"
    assert freestyle_prompt == "Summarize as a bulleted checklist."


@pytest.mark.asyncio
async def test_resolve_job_template_unknown_name_still_422s():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await _resolve_job_template(123, "long", "not-a-real-template-or-recipe", None)
    assert exc_info.value.status_code == 422
```

If `tests/test_api_jobs.py` uses a shared DB fixture (likely, given the codebase's test conventions seen in `tests/test_auth.py`), reuse that fixture rather than hand-rolling a new one — check the file's existing `async def test_` functions for the pattern (an autouse fixture initializing a temp DB is the most likely shape) and match it.

- [ ] **Step 2: Run test to verify it fails**

Run (PowerShell): `python -m pytest tests/test_api_jobs.py -k resolve_job_template -v`
Expected: FAIL — `_resolve_job_template` isn't a coroutine (calling it without `await` inside the test's `await _resolve_job_template(...)` raises `TypeError: object tuple can't be used in 'await' expression`, since the current function is sync).

- [ ] **Step 3: Write minimal implementation**

In `src/api/jobs.py`, replace `_resolve_job_template`:

```python
async def _resolve_job_template(
    chat_id: int, pipeline: str, template: str | None, freestyle_prompt: str | None
) -> tuple[str | None, str | None]:
    if pipeline == "repo":
        return None, None
    if template == "freestyle" and not freestyle_prompt:
        raise HTTPException(status_code=422, detail="freestyle_prompt is required for freestyle")
    if template and template != "freestyle" and template not in PROMPT_TEMPLATES:
        recipe = await database.get_user_template_by_name(chat_id, template)
        if recipe is None:
            raise HTTPException(status_code=422, detail="Unknown template")
        return "freestyle", recipe["extra_instructions"]
    return template, freestyle_prompt
```

Update both call sites to `await` it and pass `chat_id`:

In `_create_pipeline_job` (around line 263):
```python
    template, freestyle_prompt = await _resolve_job_template(chat_id, pipeline, template, freestyle_prompt)
```

In `enrich_job` (around line 804) — `chat_id` isn't currently in scope there; add it from the session, matching the pattern already used in `templates.py`:
```python
    chat_id: int = request.state.user["id"]
    template, freestyle_prompt = await _resolve_job_template("long", template, freestyle_prompt)
```
becomes
```python
    chat_id: int = request.state.user["id"]
    template, freestyle_prompt = await _resolve_job_template(chat_id, "long", template, freestyle_prompt)
```

- [ ] **Step 4: Run test to verify it passes**

Run (PowerShell): `python -m pytest tests/test_api_jobs.py -k resolve_job_template -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full jobs test file to catch any other caller this change missed**

Run (PowerShell): `python -m pytest tests/test_api_jobs.py -v`
Expected: PASS. If any other test calls `_resolve_job_template` synchronously, update it the same way as the two call sites above — `_resolve_job_template` must have exactly these two callers in `src/api/jobs.py` per the capability map; grep `grep -rn "_resolve_job_template" src/` to confirm no third call site exists anywhere else in `src/` before moving on.

- [ ] **Step 6: Commit**

```bash
git add src/api/jobs.py tests/test_api_jobs.py
git commit -m "fix(jobs): resolve saved recipes to their freestyle prompt"
```

---

## Task 8: "Apply to a link" UI on the Recipes page

**Files:**
- Modify: `web/app/(dashboard)/prompts/page.tsx`
- Test: check for `web/app/(dashboard)/prompts/page.test.tsx` (it exists per the capability map listing — add to it)

**Interfaces:**
- Consumes: `POST /api/jobs` (`JobCreateRequest`, already accepts `{url, template}` and now resolves a recipe name per Task 7 — no new endpoint needed).
- Produces: an "Apply to a link" mini-form on each user-recipe row, POSTing `{url, template: template.name}` to `/api/jobs`.

- [ ] **Step 1: Write the failing test**

Read `web/app/(dashboard)/prompts/page.test.tsx` first to match its existing render/mock setup for `useTemplateList`, then add:

```typescript
  it('applies a recipe to a pasted URL and shows the created job link', async () => {
    // Arrange: mock useTemplateList to return one user recipe, and mock fetch
    // for POST /api/jobs to return a created job — follow this file's
    // existing mock pattern for useTemplateList exactly (it already mocks
    // create/update/delete for the other tests in this file).
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'job123', job_id: 'job123', url: 'https://example.com/x' }),
    } as Response);

    render(<PromptsPage />);

    const urlInput = screen.getByLabelText(/apply.*url/i);
    fireEvent.change(urlInput, { target: { value: 'https://example.com/x' } });
    fireEvent.click(screen.getByRole('button', { name: /^apply$/i }));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/jobs',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ url: 'https://example.com/x', template: 'my-recipe' }),
        }),
      );
    });
    expect(await screen.findByText(/job created/i)).toBeInTheDocument();
  });
```

(This test assumes the mocked recipe from the file's existing setup is named `my-recipe`; if the existing mock uses a different name, use that name in the `body` assertion instead.)

- [ ] **Step 2: Run test to verify it fails**

Run (PowerShell, from `web/`): `npm run test:run -- prompts`
Expected: FAIL — no element matches `getByLabelText(/apply.*url/i)`.

- [ ] **Step 3: Write minimal implementation**

Read the current template-list rendering section of `web/app/(dashboard)/prompts/page.tsx` (where each `Template` from `useTemplateList()` is mapped to a row) and add, for each non-builtin template row, a small inline apply form. Add this component in the same file, above the default export:

```typescript
function ApplyRecipeForm({ templateName }: { templateName: string }) {
  const [url, setUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [createdJobId, setCreatedJobId] = useState<string | undefined>();

  const handleApply = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(undefined);
    setSubmitting(true);
    try {
      const res = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, template: templateName }),
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error((payload as { detail?: string }).detail ?? 'Apply failed');
      }
      const job = (await res.json()) as { job_id: string };
      setCreatedJobId(job.job_id);
      setUrl('');
    } catch (err: unknown) {
      setError(describeError(err, 'Apply failed'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleApply} className="mt-2 flex flex-wrap items-center gap-2">
      <label htmlFor={`apply-url-${templateName}`} className="sr-only">
        Apply recipe to URL
      </label>
      <input
        id={`apply-url-${templateName}`}
        type="url"
        required
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="Paste a link to apply this recipe to"
        className="h-8 min-w-0 flex-1 rounded-md border border-line bg-canvas px-3 text-copy text-ink placeholder:text-muted"
      />
      <button
        type="submit"
        disabled={submitting}
        className="h-8 rounded-md bg-signal px-3 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright disabled:opacity-50"
      >
        {submitting ? 'Applying…' : 'Apply'}
      </button>
      {createdJobId && (
        <span className="text-copy text-status-done">
          Job created — <a href={`/feed/${createdJobId}`} className="underline">view it</a>
        </span>
      )}
      {error && <span className="text-copy text-status-error">{error}</span>}
    </form>
  );
}
```

Then, in the existing render loop over user templates (find where `templates.filter((t) => !t.is_builtin)` or similar is mapped), add `<ApplyRecipeForm templateName={template.name} />` inside each row.

- [ ] **Step 4: Run test to verify it passes**

Run (PowerShell, from `web/`): `npm run test:run -- prompts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add "web/app/(dashboard)/prompts/page.tsx" "web/app/(dashboard)/prompts/page.test.tsx"
git commit -m "feat(recipes): add apply-to-a-link action, closing the missing path"
```

---

## Task 9: Gemini failure-rate alert via the ops bot

**Files:**
- Modify: `src/services/gemini.py`
- Test: `tests/test_gemini_client.py`

**Interfaces:**
- Consumes: `src.services.ops_bot.admin_chat_ids() -> tuple[int, ...]`, `src.services.ops_bot.send_ops_message(chat_id: int, text: str, *, parse_mode: str | None = None) -> dict` (both already exist, imported lazily inside the alert function to avoid any import-order coupling at module load).
- Produces: `_maybe_alert_gemini_failures()` (private, called from `_call_with_fallback`'s failure path); no change to any public function's signature.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gemini_client.py`, following the file's existing `monkeypatch` + `patch("src.services.gemini._call_sync", ...)` style:

```python
async def test_generate_both_keys_fail_triggers_ops_alert_after_threshold(monkeypatch):
    import src.services.gemini as gemini_module

    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")
    monkeypatch.setattr(gemini_module, "_recent_failures", [])
    monkeypatch.setattr(gemini_module, "_last_alert_at", 0.0)
    monkeypatch.setattr(gemini_module, "_FAILURE_THRESHOLD", 2)

    sent: list[tuple[int, str]] = []

    async def fake_send_ops_message(chat_id, text, **kwargs):
        sent.append((chat_id, text))
        return {}

    monkeypatch.setattr("src.services.ops_bot.admin_chat_ids", lambda: (42,))
    monkeypatch.setattr("src.services.ops_bot.send_ops_message", fake_send_ops_message)

    with patch("src.services.gemini._call_sync", side_effect=RuntimeError("boom")):
        for _ in range(2):
            with pytest.raises(gemini_module.GeminiUnavailableError):
                await gemini_module.generate("prompt", model="gemini-2.0-flash")

    assert sent == [(42, sent[0][1])]
    assert "2 calls failed" in sent[0][1]


async def test_generate_failure_alert_has_cooldown(monkeypatch):
    import src.services.gemini as gemini_module

    monkeypatch.setattr("src.config.settings.GEMINI_FREE_API_KEY", "free-key")
    monkeypatch.setattr("src.config.settings.GEMINI_PAID_API_KEY", "paid-key")
    monkeypatch.setattr(gemini_module, "_recent_failures", [])
    monkeypatch.setattr(gemini_module, "_last_alert_at", 0.0)
    monkeypatch.setattr(gemini_module, "_FAILURE_THRESHOLD", 1)

    sent_count = {"n": 0}

    async def fake_send_ops_message(chat_id, text, **kwargs):
        sent_count["n"] += 1
        return {}

    monkeypatch.setattr("src.services.ops_bot.admin_chat_ids", lambda: (42,))
    monkeypatch.setattr("src.services.ops_bot.send_ops_message", fake_send_ops_message)

    with patch("src.services.gemini._call_sync", side_effect=RuntimeError("boom")):
        for _ in range(3):
            with pytest.raises(gemini_module.GeminiUnavailableError):
                await gemini_module.generate("prompt", model="gemini-2.0-flash")

    assert sent_count["n"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run (PowerShell): `python -m pytest tests/test_gemini_client.py -k alert -v`
Expected: FAIL — `AttributeError: module 'src.services.gemini' has no attribute '_recent_failures'`

- [ ] **Step 3: Write minimal implementation**

In `src/services/gemini.py`, add `import time` to the existing import block at the top, and add this block directly above `_call_with_fallback`:

```python
# Best-effort operational alert, not a source of truth: an in-memory rolling
# window that resets on process restart. Reuses the ops bot's existing
# admin-notification channel (already used for invite approvals) instead of
# adding new monitoring infrastructure — see
# docs/superpowers/plans/2026-09-17-admin-viewer-visibility.md.
_FAILURE_WINDOW_SECONDS = 600
_FAILURE_THRESHOLD = 5
_ALERT_COOLDOWN_SECONDS = 1800
_recent_failures: list[float] = []
_last_alert_at: float = 0.0


async def _maybe_alert_gemini_failures() -> None:
    global _last_alert_at
    now = time.monotonic()
    cutoff = now - _FAILURE_WINDOW_SECONDS
    while _recent_failures and _recent_failures[0] < cutoff:
        _recent_failures.pop(0)
    if len(_recent_failures) < _FAILURE_THRESHOLD:
        return
    if now - _last_alert_at < _ALERT_COOLDOWN_SECONDS:
        return
    _last_alert_at = now

    from src.services.ops_bot import admin_chat_ids, send_ops_message

    text = (
        f"⚠️ Gemini: {len(_recent_failures)} calls failed in the last "
        f"{_FAILURE_WINDOW_SECONDS // 60} min"
    )
    for chat_id in admin_chat_ids():
        try:
            await send_ops_message(chat_id, text)
        except Exception as exc:
            log.warning("gemini.alert_send_failed", chat_id=chat_id, error=str(exc)[:120])
```

Then update `_call_with_fallback`'s raise path:

```python
async def _call_with_fallback(fn, *args, log_ok: str, log_fail: str, **fn_kwargs):
    """Try GEMINI_FREE_API_KEY then GEMINI_PAID_API_KEY. Raises GeminiUnavailableError if both fail."""
    last_error: str | None = None
    for key in [settings.GEMINI_FREE_API_KEY, settings.GEMINI_PAID_API_KEY]:
        if not key:
            continue
        try:
            result = await asyncio.to_thread(fn, *args, api_key=key, **fn_kwargs)
            log.info(log_ok)
            return result
        except Exception as exc:
            last_error = str(exc).splitlines()[0][:120]
            log.warning(log_fail, error=last_error)
    _recent_failures.append(time.monotonic())
    await _maybe_alert_gemini_failures()
    raise GeminiUnavailableError(last_error or "Both Gemini keys failed")
```

- [ ] **Step 4: Run test to verify it passes**

Run (PowerShell): `python -m pytest tests/test_gemini_client.py -k alert -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full gemini test file to confirm nothing else broke**

Run (PowerShell): `python -m pytest tests/test_gemini_client.py tests/test_gemini_photo.py -v`
Expected: PASS (all existing + 2 new tests)

- [ ] **Step 6: Commit**

```bash
git add src/services/gemini.py tests/test_gemini_client.py
git commit -m "feat(gemini): alert the ops-admin channel on a sustained failure spike"
```

---

## Self-Review

**Spec coverage:**
- Admin always sees everything → Task 1 (`is_operator`) + Tasks 5/6 (only gate applied is admin-conditional) → covered.
- Same-session toggle + separate literal viewer credential, same underlying account, starts empty, can submit real jobs → Tasks 2, 3, 4 → covered (both paths mint a session for the same `VIEWER_LOGIN_USER_ID` row; job submission needs no new work since it's an ordinary approved account going through the existing `/api/jobs`/Intake paths).
- Docs stays visible to everyone → no task needed; confirmed no gate was added anywhere touching `/doc-parser` or `/api/parsed`.
- Recipes fixed and shipped for everyone, not hidden → Tasks 7, 8 → covered.
- Newsletter Digest hidden for non-admins → Tasks 3 (backend), 5 (test), 6 (frontend) → covered.
- Gemini failure-rate alert via existing ops-bot channel, no new infra → Task 9 → covered.

**Placeholder scan:** no TBD/TODO, no "add appropriate error handling," no "similar to Task N" shortcuts — every step above has real code or a real, specific test.

**Type consistency:** `_resolve_job_template` is `async def` everywhere it's defined and called (Task 7). `Settings.is_operator` signature (`chat_id: int | None) -> bool`) is used identically in `middleware.py`, `auth.py`, and both test files. `InviteUser.is_admin`/`can_view_as`/`viewing_as` are optional booleans matching the `/api/auth/me` response shape exactly (Task 4). `VIEW_AS_COOKIE` value `"ownix_view_as"` is the same literal string in `middleware.py` and the two `set_cookie`/`delete_cookie` calls in `auth.py` (Task 3) — kept as a duplicated literal rather than a cross-module import to match this codebase's existing pattern of `COOKIE_NAME`/`"ownix_preview"` being spelled out at each call site rather than centrally re-exported everywhere it's used.

---

**Plan complete and saved to `docs/superpowers/plans/2026-09-17-admin-viewer-visibility.md`.** Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
