import { axe } from 'jest-axe';
import { expect } from 'vitest';

/** Run axe-core against a rendered container and fail with a readable
 * per-violation summary (rule id, impact, offending node) instead of jest-axe's
 * default dump — this project doesn't wire the `toHaveNoViolations` custom
 * matcher (would need its own vitest type augmentation for one call site's
 * worth of value), so this is the plain-`expect` equivalent. */
export async function expectNoAxeViolations(container: Element): Promise<void> {
  const results = await axe(container);
  if (results.violations.length === 0) return;
  const summary = results.violations
    .map(
      (v) =>
        `- [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length} node${v.nodes.length === 1 ? '' : 's'})\n` +
        v.nodes.map((n) => `    ${n.target.join(' ')}`).join('\n'),
    )
    .join('\n');
  expect.fail(`axe found ${results.violations.length} accessibility violation(s):\n${summary}`);
}
