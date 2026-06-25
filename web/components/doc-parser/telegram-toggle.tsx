'use client';

import { useRef, useState } from 'react';
import { Send } from 'lucide-react';

type State = 'off' | 'on' | 'retroactive';

export function TelegramToggle({ jobId, value = 'off' }: { jobId: string; value?: State }) {
  const [state, setState] = useState<State>(value);
  const [holding, setHolding] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fired = useRef(false); // hold completed → swallow the trailing click

  async function persist(next: State) {
    const res = await fetch(`/api/parsed/${jobId}/telegram-delivery`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ state: next }) });
    const data = await res.json();
    setState(data.telegram_delivery);
  }

  function startHold() {
    setHolding(true);
    fired.current = false;
    timer.current = setTimeout(() => { fired.current = true; persist('retroactive'); }, 1500);
  }
  function cancelHold() {
    setHolding(false);
    if (timer.current) clearTimeout(timer.current);
  }

  return <button type="button" aria-label={`Telegram delivery ${state}`} aria-pressed={state !== 'off'} onClick={(e) => { e.preventDefault(); if (fired.current) { fired.current = false; return; } persist(state === 'off' ? 'on' : 'off'); }} onPointerDown={startHold} onPointerUp={cancelHold} onPointerLeave={cancelHold} className={`relative rounded-md border p-2 transition-ui ${state === 'off' ? 'border-line text-muted' : 'border-signal text-signal'} ${holding ? 'doc-telegram-hold' : ''}`}><Send className="h-4 w-4" /></button>;
}
