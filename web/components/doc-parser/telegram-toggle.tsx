'use client';

import { useRef, useState } from 'react';

type State = 'off' | 'on' | 'retroactive';

export function TelegramToggle({ jobId, value = 'off' }: { jobId: string; value?: State }) {
  const [state, setState] = useState<State>(value);
  const [holding, setHolding] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fired = useRef(false); // hold completed → swallow the trailing click

  async function persist(next: State) {
    const res = await fetch(`/api/parsed/${jobId}/telegram-delivery`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ state: next }) });
    if (!res.ok) { console.error(`telegram-delivery PUT failed: ${res.status}`); return; } // failed PUT → keep state, surface so it's not silent
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

  const isOff = state === 'off';

  return <button type="button" aria-label={`Telegram delivery ${state}`} aria-pressed={state !== 'off'} onClick={(e) => { e.preventDefault(); if (fired.current) { fired.current = false; return; } persist(state === 'off' ? 'on' : 'off'); }} onPointerDown={startHold} onPointerUp={cancelHold} onPointerLeave={cancelHold} className={`relative flex h-[26px] w-[26px] items-center justify-center rounded-full border transition-ui ${isOff ? 'border-line' : 'border-telegram-blue'} ${holding ? 'doc-telegram-hold' : ''}`}>
    {/* Official Telegram mark (simpleicons "telegram"): a disc + plane core. On = brand
        #26A5E4 / #ffffff; off = status-cancelled / cancelled-tint so it reads as inactive.
        The disc and plane carry the affordance, so the icon needs no currentColor. */}
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true">
      <circle cx="12" cy="12" r="12" className={`transition-ui ${isOff ? 'fill-status-cancelled' : 'fill-telegram-blue'}`} />
      <path className={`transition-ui ${isOff ? 'fill-status-cancelled-tint' : 'fill-white'}`} d="M16.906 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.139-5.061 3.345-.479.329-.913.489-1.302.481-.428-.009-1.252-.242-1.865-.44-.752-.244-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
    </svg>
  </button>;
}
