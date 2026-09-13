'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { apiPut, describeError } from '@/lib/fetch-utils';

/** A settings object fetched once and written back with a full-object PUT.
 *
 * Both Settings panels that work this way (recovery notifications, accessibility)
 * had grown their own copy of the same three guards, so they live here once:
 *
 *  - `settingsRef` composes each payload from the latest optimistic value, so
 *    two onChange events firing before React re-renders between them don't both
 *    read the same stale object and drop the first one's change.
 *  - `generationRef` decides which response the UI is allowed to display, so an
 *    older overlapping request resolving last can't clobber a newer one.
 *  - `pendingSaveRef` chains each PUT onto the previous one's settlement. The
 *    endpoint is last-write-wins, so without this two in-flight PUTs can land
 *    out of send order and the older one wins *at the server* even though the
 *    UI is showing the newer value.
 */
export function useSettingsResource<T extends object>(
  url: string,
  initial: T,
  options: { errorLabel: string; onApply?: (value: T) => void },
): {
  settings: T;
  /** True only once a real GET has applied — a failed load must not leave the
   * controls editable against the hardcoded `initial` placeholder. */
  loaded: boolean;
  saving: boolean;
  error: string | undefined;
  update: (patch: Partial<T>) => Promise<void>;
} {
  const [settings, setSettings] = useState<T>(initial);
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | undefined>();

  const settingsRef = useRef(settings);
  const generationRef = useRef(0);
  const pendingSaveRef = useRef<Promise<unknown>>(Promise.resolve());

  const { errorLabel, onApply } = options;
  const onApplyRef = useRef(onApply);
  useEffect(() => {
    onApplyRef.current = onApply;
  });

  const apply = useCallback((value: T) => {
    settingsRef.current = value;
    setSettings(value);
    onApplyRef.current?.(value);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    // nosemgrep -- same-origin relative API path; every call site passes a static literal
    fetch(url, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`Failed to load ${errorLabel}`);
        return (await response.json()) as T;
      })
      .then((value) => {
        if (controller.signal.aborted) return;
        apply(value);
        setLoaded(true);
      })
      .catch((caught) => {
        if (
          controller.signal.aborted ||
          (caught instanceof Error && caught.name === 'AbortError')
        )
          return;
        setError(describeError(caught, `Failed to load ${errorLabel}`));
      });
    return () => controller.abort();
  }, [url, errorLabel, apply]);

  const update = useCallback(
    async (patch: Partial<T>) => {
      const generation = ++generationRef.current;
      const previous = settingsRef.current;
      const next = { ...settingsRef.current, ...patch };
      apply(next);
      setSaving(true);
      setError(undefined);

      const run = pendingSaveRef.current.then(() =>
        apiPut<T>(url, next, `Failed to save ${errorLabel}`),
      );
      // Swallowed so a failed PUT doesn't poison the chain for the next update.
      pendingSaveRef.current = run.catch(() => undefined);

      try {
        const saved = await run;
        if (generation !== generationRef.current) return;
        apply(saved);
      } catch (caught) {
        if (generation !== generationRef.current) return;
        apply(previous);
        setError(describeError(caught, `Failed to save ${errorLabel}`));
      } finally {
        if (generation === generationRef.current) setSaving(false);
      }
    },
    [url, errorLabel, apply],
  );

  return { settings, loaded, saving, error, update };
}
