// Narrow scope on purpose (docs/plans/2026-08-25-mutation-testing-research.md): five
// already-tested, pure-logic lib files, not web/components/** (RTL/MSW rendering would
// multiply per-mutant runtime and flakiness before this scope has proven the workflow).
/** @type {import('@stryker-mutator/api/core').PartialStrykerOptions} */
export default {
  testRunner: 'vitest',
  vitest: {
    configFile: 'vitest.config.ts',
  },
  mutate: [
    'lib/feed-thumbnail-preload.ts',
    'lib/job-detail-utils.ts',
    'lib/parse-batch-links.ts',
    'lib/polling.ts',
    'lib/share-target.ts',
  ],
  // typescript-checker runs a whole-project `tsc` dry run and currently fails on
  // pre-existing type errors in unrelated test files (app/(dashboard)/feed/page.test.tsx,
  // app/(dashboard)/jobs/[id]/page.test.tsx) that npm test/Vitest never catches today.
  // Re-enable once that debt is fixed separately — not in scope for these 5 lib files.
  reporters: ['clear-text', 'progress', 'html'],
  thresholds: { high: 80, low: 60, break: 50 },
  incremental: true,
  // Default (5min) isn't enough for this repo's first, uncached dry run — the
  // whole-project jsdom/RTL suite under perTest coverage instrumentation is slow.
  dryRunTimeoutMinutes: 15,
};
