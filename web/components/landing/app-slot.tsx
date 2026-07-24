'use client';

import { useEffect, useState } from 'react';
import { useReducedMotion } from '@/lib/hooks/useReducedMotion';
import { YouTubeIcon } from '@/components/svg/youtube-icon';
import { YouTubeShortsIcon } from '@/components/svg/youtube-shorts-icon';
import { InstagramIcon } from '@/components/svg/instagram-icon';
import { TikTokIcon } from '@/components/svg/tiktok-icon';
import { GitHubIcon } from '@/components/svg/github-icon';
import { PDFIcon } from '@/components/svg/pdf-icon';

const icons = [
  YouTubeIcon,
  InstagramIcon,
  PDFIcon,
  TikTokIcon,
  YouTubeShortsIcon,
  GitHubIcon,
];

/** Inline 22px icon slot in the hero copy that cross-fades through the
 * apps you can share from. Under reduced motion it stays on the first icon.
 *
 * This sits inside the hero paragraph — the page's LCP element — so the
 * server-rendered/initial-paint markup deliberately mounts only the active
 * icon instead of all six stacked ones. The other five (needed for the
 * cross-fade cycle) mount only after hydration, via the standard
 * client-only-enhancement `mounted` flag: it starts `false` on both server
 * and first client render (no hydration mismatch), then flips `true` inside
 * `useEffect`, safely after the critical first paint has already happened. */
export function AppSlot() {
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
    <>
      <span
        aria-hidden="true"
        className="inline-grid h-[22px] w-[22px] align-[-4px]"
      >
        {mounted ? (
          icons.map((Icon, i) => (
            <Icon
              key={i}
              className={`col-start-1 row-start-1 h-[22px] w-[22px] text-ink transition-opacity duration-[400ms] ease-out ${
                i === active ? 'opacity-100' : 'opacity-0'
              }`}
            />
          ))
        ) : (
          <ActiveIcon className="col-start-1 row-start-1 h-[22px] w-[22px] text-ink opacity-100" />
        )}
      </span>
      <span className="sr-only">any app</span>
    </>
  );
}
