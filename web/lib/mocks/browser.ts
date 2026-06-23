import { setupWorker } from 'msw/browser';
import { makeHandlers, type Seed } from './handlers';

// Idempotent: StrictMode double-invoke / Fast Refresh must not call start()
// twice (the second call throws "already enabled network").
let started: Promise<unknown> | null = null;
export function startWorker() {
  if (!started) started = init();
  return started;
}

// Seed is fetched (not imported) so the 1.3MB snapshot never enters the bundle
// and the prod build doesn't depend on the gitignored web/public/seed.json.
async function init() {
  const seed = (await fetch('/seed.json').then((r) => r.json())) as Seed;
  const worker = setupWorker(...makeHandlers(seed));
  await worker.start({ onUnhandledRequest: 'bypass' });
}
