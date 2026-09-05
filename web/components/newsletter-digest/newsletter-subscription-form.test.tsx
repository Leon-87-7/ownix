// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
import { NewsletterSubscriptionForm } from './newsletter-subscription-form';

describe('NewsletterSubscriptionForm', () => {
  it('submits a trimmed name and lowercased sender email', async () => {
    const onSubmit = vi.fn();
    render(<NewsletterSubscriptionForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: '  Morning Brief  ' } });
    fireEvent.change(screen.getByLabelText('Sender email'), {
      target: { value: '  Editor@Example.COM  ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({
        name: 'Morning Brief',
        sender_email: 'editor@example.com',
      }),
    );
  });

  it('renders a server error as an alert', () => {
    render(<NewsletterSubscriptionForm onSubmit={vi.fn()} error="Alias already exists" />);

    expect(screen.getByRole('alert')).toHaveTextContent('Alias already exists');
  });

  it('clears the fields after a successful submit', async () => {
    const onSubmit = vi.fn().mockResolvedValue(true);
    render(<NewsletterSubscriptionForm onSubmit={onSubmit} />);

    const nameInput = screen.getByLabelText('Name') as HTMLInputElement;
    const senderInput = screen.getByLabelText('Sender email') as HTMLInputElement;
    fireEvent.change(nameInput, { target: { value: 'Morning Brief' } });
    fireEvent.change(senderInput, { target: { value: 'editor@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));

    await waitFor(() => expect(nameInput.value).toBe(''));
    expect(senderInput.value).toBe('');
  });

  it('preserves the fields after a failed submit', async () => {
    const onSubmit = vi.fn().mockResolvedValue(false);
    render(<NewsletterSubscriptionForm onSubmit={onSubmit} />);

    const nameInput = screen.getByLabelText('Name') as HTMLInputElement;
    const senderInput = screen.getByLabelText('Sender email') as HTMLInputElement;
    fireEvent.change(nameInput, { target: { value: 'Morning Brief' } });
    fireEvent.change(senderInput, { target: { value: 'editor@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(nameInput.value).toBe('Morning Brief');
    expect(senderInput.value).toBe('editor@example.com');
  });
});
