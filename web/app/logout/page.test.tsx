// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import LogoutPage from './page';

describe('LogoutPage', () => {
  it('confirms logout and links back to login', () => {
    render(<LogoutPage />);

    expect(screen.getByText('Session closed')).toBeInTheDocument();
    expect(
      screen.getByText(
        "Ownix is signed out. Telegram may still remember this browser's Telegram account for the next sign-in.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Sign in with Telegram' }),
    ).toHaveAttribute('href', '/login');
  });
});
