'use client';

import { useEffect, useState } from 'react';
import { useReducedMotion } from '@/lib/hooks/useReducedMotion';
import { TelegramIcon } from '@/components/svg/telegram-icon';
import { DiscordIcon } from '@/components/svg/discord-icon';
import { ChromeIcon } from '@/components/svg/chrome-icon';

const icons = [TelegramIcon, DiscordIcon, ChromeIcon];

/** Cross-fading destination icon for the invite section's "FROM ... TO" strip —
 * same mechanism as AppSlot, mirrored for the send-to side (Telegram, Discord,
 * the Chrome extension) instead of the share-from side. */
export function DestinationSlot() {
  const [active, setActive] = useState(0);
  const [mounted, setMounted] = useState(false);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (reducedMotion) {
      setActive(0);
      return;
    }
    const id = setInterval(
      () => setActive((i) => (i + 1) % icons.length),
      2600,
    );
    return () => clearInterval(id);
  }, [reducedMotion]);

  const ActiveIcon = icons[active];

  return (
    <span
      aria-hidden="true"
      className="inline-grid h-6 w-6 shrink-0"
    >
      {mounted ? (
        icons.map((Icon, i) => (
          <Icon
            key={i}
            className={`col-start-1 row-start-1 h-6 w-6 transition-opacity duration-[400ms] ease-out ${
              i === active ? 'opacity-100' : 'opacity-0'
            }`}
          />
        ))
      ) : (
        <ActiveIcon className="col-start-1 row-start-1 h-6 w-6 opacity-100" />
      )}
    </span>
  );
}
