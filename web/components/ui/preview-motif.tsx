import { useId } from 'react';
import OwnixLogo from '@/app/ownix-logo.svg';

export default function PreviewMotif({
  label,
  ariaLabel,
  className,
  size = 'default',
  treatment = 'default',
}: {
  label: string;
  /** Screen-reader name when the ring text alone is too terse. */
  ariaLabel?: string;
  className: string;
  size?: 'default' | 'fill';
  treatment?: 'default' | 'hero';
}) {
  const ringId = useId();
  const gradientId = useId();
  const motifSize = size === 'fill' ? 'h-full w-full' : 'h-44 w-44';
  const logoSize =
    size === 'fill' ? 'h-[32%] w-[32%]' : 'h-14 w-14';
  const logoAnimation =
    treatment === 'hero'
      ? 'motion-safe:animate-[ownix-logo-cycle_35s_linear_infinite]'
      : 'motion-safe:animate-[ownix-logo-cycle_7s_linear_infinite]';
  const ringAnimation =
    treatment === 'hero'
      ? 'motion-safe:animate-[spin_35s_linear_infinite]'
      : 'motion-safe:animate-[spin_14s_linear_infinite]';

  return (
    <div
      role="status"
      aria-label={ariaLabel ?? label}
      className={`flex items-center justify-center ${className}`}
    >
      <div className={`relative max-h-full max-w-full ${motifSize}`}>
        <OwnixLogo
          aria-hidden="true"
          focusable="false"
          className={`absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 ${logoAnimation} ${logoSize}`}
        />
        <svg
          viewBox="0 0 176 176"
          aria-hidden="true"
          className={`absolute inset-0 h-full w-full origin-center motion-reduce:animate-none ${ringAnimation}`}
        >
          <defs>
            <path
              id={ringId}
              d="M 88,88 m -66,0 a 66,66 0 1,1 132,0 a 66,66 0 1,1 -132,0"
            />
            <linearGradient
              id={gradientId}
              x1="22"
              y1="22"
              x2="154"
              y2="154"
              gradientUnits="userSpaceOnUse"
              gradientTransform="rotate(35 88 88)"
            >
              <stop offset="0" stopColor="#a57534" />
              <stop offset="0.32" stopColor="#efb566" />
              <stop offset="0.66" stopColor="#9ec9ff" />
              <stop offset="1" stopColor="#649ca1" />
            </linearGradient>
          </defs>
          <text
            fill={treatment === 'hero' ? `url(#${gradientId})` : undefined}
            className={`${treatment === 'hero' ? '' : 'fill-muted'} font-mono text-micro font-medium tracking-[0.18em]`}
          >
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
