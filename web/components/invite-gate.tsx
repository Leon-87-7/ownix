"use client";

import { createContext, useContext, FormEvent, KeyboardEvent as ReactKeyboardEvent, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Spinner } from '@/components/ui';

type UserStatus = "pending" | "approved" | "blocked";

export interface InviteUser {
  id: number;
  first_name?: string;
  username?: string | null;
  photo_url?: string | null;
  email?: string | null;
  status: UserStatus;
}

// Session identity (CONTEXT.md): the gate's single /api/auth/me fetch is the
// source of truth — consumers read it from here instead of re-fetching.
const SessionUserContext = createContext<InviteUser | null>(null);

export function useSessionUser(): InviteUser | null {
  return useContext(SessionUserContext);
}

const MOCK_SESSION_USER: InviteUser = {
  id: 0,
  first_name: "Mock User",
  username: "mock_user",
  photo_url: null,
  email: "mock@example.com",
  status: "approved",
};

function mockModeEnabled(): boolean {
  return (
    process.env.NODE_ENV !== "production" &&
    process.env.NEXT_PUBLIC_API_MOCK === "1"
  );
}

function GateScreen({ status }: { status: Exclude<UserStatus, 'approved'> }) {
  const blocked = status === 'blocked';
  return (
    <div className="flex min-h-[calc(100vh-3rem)] items-center justify-center px-4">
      <section className="w-full max-w-md rounded-lg border border-line bg-surface p-6">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">
          {blocked ? "Access blocked" : "Pending approval"}
        </h1>
        <p className="mt-2 text-sm leading-6 text-body">
          {blocked
            ? "This Telegram account cannot access Ownix."
            : "Your request is waiting for approval. Ownix is invite-only while it is young."}
        </p>
      </section>
    </div>
  );
}

function EmailModal({
  onSaved,
}: {
  onSaved: (email: string, status: UserStatus) => void;
}) {
  const [email, setEmail] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    inputRef.current?.focus();
    return () => previousFocus?.focus();
  }, []);

  const trapTab = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Tab' || !dialogRef.current) return;
    const focusables = dialogRef.current.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = email.trim().toLowerCase();
    if (!normalized) {
      setError('Enter an email address.');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const res = await fetch('/api/auth/email', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: normalized }),
      });

      if (!res.ok) {
        setError('Could not save email.');
        return;
      }

      const data = (await res.json()) as { email: string; status: UserStatus };
      onSaved(data.email, data.status);
    } catch {
      setError('Could not save email. Check your connection and try again.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-canvas/80 px-4">
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="invite-email-title"
        onKeyDown={trapTab}
        className="w-full max-w-sm rounded-lg border border-line bg-surface p-5 shadow-overlay"
      >
        <h2 id="invite-email-title" className="text-lg font-semibold text-ink">Email required</h2>
        <p className="mt-2 text-sm leading-6 text-body">
          Ownix is invite-only while it is young. Add the email we should use
          to review this Telegram account and follow up for feedback.
        </p>
        <form className="mt-4 space-y-3" onSubmit={submit}>
          <label
            className="block text-sm font-medium text-body"
            htmlFor="invite-email"
          >
            Email
          </label>
          <input
            ref={inputRef}
            id="invite-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="h-9 w-full rounded-md border border-line bg-canvas px-3 text-sm text-ink transition-ui placeholder:text-muted focus:border-signal"
            placeholder="you@example.com"
            autoComplete="email"
            required
            aria-describedby={error ? 'invite-email-error' : undefined}
          />
          {error && (
            <p id="invite-email-error" role="alert" className="text-sm text-status-error">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={saving}
            className="h-8 rounded-md bg-signal px-3 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright disabled:cursor-not-allowed disabled:bg-raised disabled:text-muted"
          >
            {saving ? "Saving..." : "Save email"}
          </button>
        </form>
      </section>
    </div>
  );
}

export function InviteGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<InviteUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (mockModeEnabled()) {
      setUser(MOCK_SESSION_USER);
      setLoading(false);
      return;
    }

    let alive = true;
    fetch("/api/auth/me")
      .then(async (res) => {
        if (res.status === 401 || res.status === 403) {
          router.replace('/login');
          return null;
        }
        if (!res.ok) throw new Error('session check failed');
        return (await res.json()) as InviteUser;
      })
      .then((next) => {
        if (alive && next) setUser(next);
      })
      .catch(() => {
        if (alive) setLoadError('Could not check access. Check your connection and try again.');
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [router]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center gap-2 bg-canvas text-sm text-body">
        <Spinner />
        Checking access…
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
        <section className="w-full max-w-md rounded-lg border border-line bg-surface p-6">
          <h1 className="text-lg font-semibold text-ink">Could not check access</h1>
          <p className="mt-2 text-sm leading-6 text-body">{loadError}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-4 h-8 rounded-md bg-signal px-3 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright"
          >
            Retry
          </button>
        </section>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  const needsEmail = !user.email;
  const approved = user.status === 'approved';
  const canShowDashboard = approved && !needsEmail;

  return (
    <SessionUserContext.Provider value={user}>
      {canShowDashboard ? children : user.status === 'blocked' ? (
        <GateScreen status="blocked" />
      ) : user.status === 'pending' ? (
        <GateScreen status="pending" />
      ) : null}
      {needsEmail && user.status !== 'blocked' && (
        <EmailModal
          onSaved={(email, status) =>
            setUser((prev) => prev && { ...prev, email, status })
          }
        />
      )}
    </SessionUserContext.Provider>
  );
}
