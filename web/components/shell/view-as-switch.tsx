'use client';

import { Eye, EyeOff } from 'lucide-react';
import { useState } from 'react';
import { useSessionUser } from '@/components/shell/invite-gate';

export default function ViewAsSwitch() {
  const user = useSessionUser();
  const [pending, setPending] = useState(false);
  if (!user?.can_view_as) return null;

  const viewing = user.viewing_as === true;
  const toggle = async () => {
    setPending(true);
    const response = await fetch('/api/auth/view-as', {
      method: viewing ? 'DELETE' : 'POST',
    });
    if (response.ok) window.location.reload();
    else setPending(false);
  };
  const label = viewing ? 'Exit viewer mode' : 'View Ownix as a member';
  const Icon = viewing ? EyeOff : Eye;
  return (
    <button
      type="button"
      onClick={toggle}
      disabled={pending}
      aria-label={label}
      title={label}
      className="fixed bottom-10 right-10 z-50 flex size-12 items-center justify-center rounded-full border border-line bg-surface text-ink shadow-overlay transition-ui hover:border-signal hover:text-signal focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal disabled:text-muted"
    >
      <Icon className="size-5" aria-hidden="true" />
    </button>
  );
}
