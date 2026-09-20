import { CountUp } from '@/components/landing/count-up';

const tiles: [string, number][] = [
  ['Items indexed', 624],
  ['Links extracted', 1210],
  ['Videos saved', 462],
  ['Repos collected', 59],
];

export function StatsSection() {
  return (
    <section
      aria-labelledby="stats"
      className="border-t border-line bg-canvas-gradient py-12 sm:bg-canvas"
    >
      <div className="mx-auto max-w-[960px] px-6">
        <h2
          id="stats"
          className="mb-4 font-title text-[clamp(1.375rem,3.4vw,1.75rem)] font-semibold leading-tight tracking-[-0.25px] text-ink"
        >
          It compounds - and it&apos;s yours.
        </h2>
        <p className="text-pretty mb-6 max-w-[58ch] text-prose leading-relaxed">
          Three months of casual saving, no effort beyond the share
          button:
        </p>

        {/* Below 360px the two-line mono captions misalign the values —
          stack the tiles instead. */}
        <div className="mb-6 grid grid-cols-1 gap-3 min-[360px]:grid-cols-2 md:grid-cols-4">
          {tiles.map(([cap, val], i) => (
            <div
              key={cap}
              className="rounded-lg border border-line bg-surface px-4 py-3"
            >
              <span className="mb-1 block font-mono text-mono-label font-medium uppercase tracking-[0.4px] text-muted">
                {cap}
              </span>
              <span className="text-stat tracking-stat font-semibold leading-[1.1] text-ink tabular-nums">
                <CountUp
                  value={val}
                  delay={i * 80}
                />
              </span>
            </div>
          ))}
        </div>

        <p className="text-pretty mb-6 max-w-[58ch] text-prose leading-relaxed">
          As I was building Ownix I once needed a frontend component
          library I&apos;d seen weeks earlier - couldn&apos;t remember
          its name, just a glimpse of the homepage. Searched my Index
          instead of my memory, and there it was in the link table.
        </p>

        <p className="text-pretty mb-6 max-w-[58ch] text-prose leading-relaxed">
          Don&apos;t remember the title either? Search by tag,
          thumbnail, or whatever you do remember, and pull up every
          link a video ever mentioned - long after the video itself
          scrolled off your feed.
        </p>
      </div>
    </section>
  );
}
