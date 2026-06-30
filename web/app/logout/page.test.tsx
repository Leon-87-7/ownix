// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import LogoutPage from './page';

describe('LogoutPage', () => {
  it('confirms logout and links back to login', () => {
    render(<LogoutPage />);

    expect(screen.getByText('See you soon')).toBeInTheDocument();
    expect(
      screen.getByText("You've been signed out successfully."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Sign in with Telegram' }),
    ).toHaveAttribute('href', '/login');
  });
});
