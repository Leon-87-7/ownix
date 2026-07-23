import { useId } from 'react';
import OwnixLogo from '@/app/ownix-logo.svg';

export default function PreviewMotif({
  label,
  ariaLabel,
  className,
}: {
  label: string;
  /** Screen-reader name when the ring text alone is too terse. */
  ariaLabel?: string;
  className: string;
}) {
  const ringId = useId();

  return (
    <div
      role="status"
      aria-label={ariaLabel ?? label}
      className={`flex items-center justify-center ${className}`}
    >
      <div className="relative h-44 w-44 max-h-full max-w-full">
        <OwnixLogo
          aria-hidden="true"
          focusable="false"
          className="absolute left-1/2 top-1/2 h-14 w-14 -translate-x-1/2 -translate-y-1/2 text-ink"
        />
        <svg
          viewBox="0 0 176 176"
          aria-hidden="true"
          className="absolute inset-0 h-full w-full origin-center motion-safe:animate-[spin_14s_linear_infinite] motion-reduce:animate-none"
        >
          <defs>
            <path
              id={ringId}
              d="M 88,88 m -66,0 a 66,66 0 1,1 132,0 a 66,66 0 1,1 -132,0"
            />
          </defs>
          <text className="fill-muted font-mono text-[10px] font-medium tracking-[0.18em]">
            <textPath
              href={`#${ringId}`}
              startOffset="0"
              textLength="408"
              lengthAdjust="spacing"
            >
              ◉ {label} ◉ {label}
            </textPath>
          </text>
        </svg>
      </div>
    </div>
  );
}
