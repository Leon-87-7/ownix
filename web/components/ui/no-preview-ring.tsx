import { useId } from "react";
import OwnixLogo from "@/app/ownix-logo.svg";

// ponytail: djb2 string hash — deterministic per-job placement, not crypto
function hash(s: string) {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0;
  return h;
}

export function ringGeometry(seed: string) {
  const h = hash(seed);
  const size = 112 + ((h >> 14) % 65); // px diameter, 112–176
  // ponytail: edge-hugging placement — the ring center sits 0.35–0.45 radii
  // inside one card edge: the outer ring text clips, but the center logo
  // (32% of the diameter) always stays fully visible. Approximate, not exact
  // circular-segment math.
  const edge = h % 4; // 0 left, 1 right, 2 top, 3 bottom
  const along = `${25 + ((h >> 2) % 51)}%`; // 25–75% along the edge, avoids corners
  const t = 0.35 + ((h >> 9) % 11) / 100; // 0.35 … 0.45 of radius inside
  const inset = Math.round((size / 2) * t);
  const near = `${inset}px`;
  const far = `calc(100% - ${inset}px)`;
  return {
    left: edge === 0 ? near : edge === 1 ? far : along,
    top: edge === 2 ? near : edge === 3 ? far : along,
    size,
    angle: (h >> 21) % 360, // static rotation of the ring text
  };
}

// Static sibling of PreviewMotif: a "no preview" stamp for empty thumbnails,
// seeded by job id so each card gets its own stable position/size/rotation.
export function NoPreviewRing({
  seed,
  label,
}: {
  seed: string;
  label?: string | null;
}) {
  const ringId = useId();
  const { left, top, size, angle } = ringGeometry(seed);
  const phrase = `◉ NO PREVIEW ${label ? `◉ ${label.toUpperCase()} ` : ""}`;

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute opacity-60"
      style={{
        left,
        top,
        width: size,
        height: size,
        transform: "translate(-50%, -50%)",
      }}
    >
      <OwnixLogo
        aria-hidden="true"
        focusable="false"
        className="absolute left-1/2 top-1/2 h-[32%] w-[32%] -translate-x-1/2 -translate-y-1/2 text-ink"
      />
      <svg
        viewBox="0 0 176 176"
        className="absolute inset-0 h-full w-full origin-center"
        style={{ transform: `rotate(${angle}deg)` }}
      >
        <defs>
          <path
            id={ringId}
            d="M 88,88 m -66,0 a 66,66 0 1,1 132,0 a 66,66 0 1,1 -132,0"
          />
        </defs>
        <text className="fill-muted font-mono text-[15px] font-medium tracking-[0.18em]">
          <textPath
            href={`#${ringId}`}
            startOffset="0"
            textLength="408"
            lengthAdjust="spacing"
          >
            {phrase}
            {phrase}
          </textPath>
        </text>
      </svg>
    </div>
  );
}
