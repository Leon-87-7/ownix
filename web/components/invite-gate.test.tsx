// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@/test/render";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { InviteGate, useSessionUser } from "./invite-gate";

const navigationMock = vi.hoisted(() => ({
  replace: vi.fn(),
  router: null as null | { replace: ReturnType<typeof vi.fn> },
}));
navigationMock.router = { replace: navigationMock.replace };

vi.mock("next/navigation", () => ({
  useRouter: () => navigationMock.router,
}));

beforeEach(() => {
  navigationMock.replace.mockClear();
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("InviteGate", () => {
  it("bypasses the auth fetch in local mock mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MOCK", "1");
    vi.stubGlobal("fetch", vi.fn());

    render(
      <InviteGate>
        <div>Dashboard feed</div>
      </InviteGate>,
    );

    expect(await screen.findByText("Dashboard feed")).toBeTruthy();
    expect(vi.mocked(fetch)).not.toHaveBeenCalled();
    expect(navigationMock.replace).not.toHaveBeenCalledWith("/login");
  });

  it("renders dashboard children for approved users with an email", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              id: 1,
              email: "user@example.com",
              status: "approved",
            }),
            { status: 200 },
          ),
      ),
    );

    render(
      <InviteGate>
        <div>Dashboard feed</div>
      </InviteGate>,
    );

    expect(await screen.findByText("Dashboard feed")).toBeTruthy();
  });

  it("exposes the fetched user to children via useSessionUser", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              id: 1,
              first_name: "Leon",
              username: "leon87",
              photo_url: "https://t.me/i/userpic/leon.jpg",
              email: "user@example.com",
              status: "approved",
            }),
            { status: 200 },
          ),
      ),
    );

    function WhoAmI() {
      const user = useSessionUser();
      return <div>{user ? `${user.first_name} (${user.photo_url})` : "no user"}</div>;
    }

    render(
      <InviteGate>
        <WhoAmI />
      </InviteGate>,
    );

    expect(
      await screen.findByText("Leon (https://t.me/i/userpic/leon.jpg)"),
    ).toBeTruthy();
    // Exactly one identity fetch — the sidebar must not add a second one.
    expect(vi.mocked(fetch).mock.calls.filter(([url]) => url === "/api/auth/me")).toHaveLength(1);
  });

  it("shows the pending screen instead of dashboard content for pending users", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              id: 1,
              email: "user@example.com",
              status: "pending",
            }),
            { status: 200 },
          ),
      ),
    );

    render(
      <InviteGate>
        <div>Dashboard feed</div>
      </InviteGate>,
    );

    expect(await screen.findByText("Pending approval")).toBeTruthy();
    expect(screen.queryByText("Dashboard feed")).toBeNull();
  });

  it("shows a one-field email modal once and persists the email", async () => {
    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        if (String(input) === "/api/auth/email" && init?.method === "PUT") {
          return new Response(
            JSON.stringify({ email: "user@example.com", status: "pending" }),
            { status: 200 },
          );
        }
        return new Response(
          JSON.stringify({ id: 1, email: null, status: "pending" }),
          { status: 200 },
        );
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <InviteGate>
        <div>Dashboard feed</div>
      </InviteGate>,
    );

    const input = await screen.findByLabelText("Email");
    fireEvent.change(input, { target: { value: "User@Example.COM" } });
    fireEvent.click(screen.getByRole("button", { name: /save email/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/auth/email",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ email: "user@example.com" }),
        }),
      );
    });
    await waitFor(() => {
      expect(screen.queryByLabelText("Email")).toBeNull();
    });
    expect(screen.getByText("Pending approval")).toBeTruthy();
  });

  it('does not redirect on transient session-check failure and shows retry', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('server error', { status: 500 })));

    render(<InviteGate><div>Dashboard feed</div></InviteGate>);

    expect(await screen.findByText('Could not check access')).toBeTruthy();
    expect(screen.getByRole('button', { name: /retry/i })).toBeTruthy();
    expect(navigationMock.replace).not.toHaveBeenCalledWith('/login');
    expect(screen.queryByText('Dashboard feed')).toBeNull();
  });

  it('resets saving and shows an error when email submission rejects', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === '/api/auth/email' && init?.method === 'PUT') {
        throw new Error('offline');
      }
      return new Response(JSON.stringify({
        id: 1,
        email: null,
        status: 'pending',
      }), { status: 200 });
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<InviteGate><div>Dashboard feed</div></InviteGate>);

    const input = await screen.findByLabelText('Email');
    fireEvent.change(input, { target: { value: 'User@Example.COM' } });
    fireEvent.click(screen.getByRole('button', { name: /save email/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not save email/i);
    expect(screen.getByRole('button', { name: /save email/i })).not.toBeDisabled();
  });

  it('marks the email modal as a dialog and focuses the email input', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({
        id: 1,
        email: null,
        status: 'pending',
      }), { status: 200 })),
    );

    render(<InviteGate><div>Dashboard feed</div></InviteGate>);

    const dialog = await screen.findByRole('dialog', { name: /email required/i });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(screen.getByLabelText('Email')).toHaveFocus();
  });

  it('does not mount dashboard children for approved users without email', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({
        id: 1,
        email: null,
        status: 'approved',
      }), { status: 200 })),
    );

    render(<InviteGate><div>Dashboard feed</div></InviteGate>);

    expect(await screen.findByRole('dialog', { name: /email required/i })).toBeTruthy();
    expect(screen.queryByText('Pending approval')).toBeNull();
    expect(screen.queryByText('Dashboard feed')).toBeNull();
  });

  it('does not show the email modal for blocked users without email', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({
        id: 1,
        email: null,
        status: 'blocked',
      }), { status: 200 })),
    );

    render(<InviteGate><div>Dashboard feed</div></InviteGate>);

    expect(await screen.findByText('Access blocked')).toBeTruthy();
    expect(screen.queryByRole('dialog', { name: /email required/i })).toBeNull();
    expect(screen.queryByLabelText('Email')).toBeNull();
  });

});
