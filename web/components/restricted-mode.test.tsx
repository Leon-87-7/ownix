// @vitest-environment jsdom
import { fireEvent, render, screen } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
import { AppHeader } from './app-header';
import { SubmitJobProvider, useSubmitJob } from './submit-job';
import { RestrictedModeProvider } from '@/lib/restricted/context';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

function Providers({
  restricted,
  children,
}: {
  restricted: boolean;
  children: React.ReactNode;
}) {
  return (
    <RestrictedModeProvider restricted={restricted}>
      <SubmitJobProvider>{children}</SubmitJobProvider>
    </RestrictedModeProvider>
  );
}

function OpenSubmitButton() {
  const { setOpen, open } = useSubmitJob();
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open submit
      </button>
      <span>{open ? 'submit open' : 'submit closed'}</span>
    </>
  );
}

function OpenCommandButton() {
  const { openCommand } = useSubmitJob();
  return (
    <button type="button" onClick={openCommand}>
      Open command
    </button>
  );
}

describe('AppHeader in Restricted mode (ADR-0035 §6)', () => {
  it('replaces the rhythm block with the restricted banner', () => {
    render(
      <Providers restricted>
        <AppHeader />
      </Providers>,
    );
    expect(screen.getByText('Restricted mode on')).toBeTruthy();
    expect(
      screen.getByText("Now viewing a read-only sample of Leon's Index"),
    ).toBeTruthy();
    const getAccess = screen.getByRole('link', { name: 'Get access' });
    expect(getAccess.getAttribute('href')).toBe('/login?from=restricted');
    expect(screen.queryByText('Collect.')).toBeNull();
  });

  it('keeps the rhythm block outside Restricted mode', () => {
    render(
      <Providers restricted={false}>
        <AppHeader />
      </Providers>,
    );
    expect(screen.getByText('Collect.')).toBeTruthy();
    expect(screen.queryByText('Restricted mode on')).toBeNull();
  });
});

describe('blocked actions show the global toast (ADR-0035 §5)', () => {
  it('blocks Submit and shows the restricted toast', () => {
    render(
      <Providers restricted>
        <OpenSubmitButton />
      </Providers>,
    );
    fireEvent.click(screen.getByText('Open submit'));
    expect(screen.getByText('submit closed')).toBeTruthy();
    expect(screen.getByRole('status').textContent).toContain(
      'Restricted mode on',
    );
    expect(
      screen.getByText('Sign in to submit URLs to your own Index.'),
    ).toBeTruthy();
  });

  it('blocks the command launcher and shows the restricted toast', () => {
    render(
      <Providers restricted>
        <OpenCommandButton />
      </Providers>,
    );
    fireEvent.click(screen.getByText('Open command'));
    expect(
      screen.getByText('Sign in to run commands on your own Index.'),
    ).toBeTruthy();
  });

  it('leaves Submit usable outside Restricted mode', () => {
    render(
      <Providers restricted={false}>
        <OpenSubmitButton />
      </Providers>,
    );
    fireEvent.click(screen.getByText('Open submit'));
    expect(screen.getByText('submit open')).toBeTruthy();
  });
});
