'use client';

import { useEffect, useState } from 'react';
import { useTemplateList } from '@/lib/hooks/useTemplateList';

const GEMINI_RECIPES = [
  'summary',
  'method',
  'technical',
  'review',
  'narrative',
] as const;

function useDesktopViewport() {
  const [desktop, setDesktop] = useState(false);
  useEffect(() => {
    const media = window.matchMedia('(min-width: 768px)');
    const update = () => setDesktop(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  return desktop;
}

function RecipeChoices({
  onSubmit,
  descriptions = {},
  disabled = false,
}: {
  onSubmit: (template: string, prompt?: string) => Promise<void>;
  descriptions?: Record<string, string>;
  disabled?: boolean;
}) {
  const [freestyle, setFreestyle] = useState(false);
  const [prompt, setPrompt] = useState('');
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap justify-center gap-2">
        {GEMINI_RECIPES.map((recipe) => (
          <button
            key={recipe}
            type="button"
            disabled={disabled}
            onClick={() => void onSubmit(recipe)}
            className={`${descriptions[recipe] ? 'h-auto w-full py-2 text-left' : 'h-8'} rounded-md border border-line px-3 text-button font-medium capitalize text-ink transition-ui hover:bg-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal`}
          >
            <span className="block">{recipe}</span>
            {descriptions[recipe] && (
              <span className="mt-1 block text-sm font-normal normal-case text-body">
                {descriptions[recipe]}
              </span>
            )}
          </button>
        ))}
        <button
          type="button"
          disabled={disabled}
          onClick={() => setFreestyle(true)}
          className="h-8 rounded-md border border-line px-3 text-button font-medium text-ink transition-ui hover:bg-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal"
        >
          Freestyle
        </button>
      </div>
      {freestyle && (
        <div className="space-y-2">
          <label
            htmlFor="gemini-freestyle"
            className="block text-label font-medium text-body"
          >
            Freestyle instructions
          </label>
          <textarea
            id="gemini-freestyle"
            value={prompt}
            disabled={disabled}
            onChange={(event) => setPrompt(event.target.value)}
            maxLength={4000}
            rows={4}
            className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal"
          />
          <button
            type="button"
            disabled={disabled || !prompt.trim()}
            onClick={() => void onSubmit('freestyle', prompt.trim())}
            className="h-8 rounded-md bg-signal px-3 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright disabled:bg-raised disabled:text-muted"
          >
            Run Freestyle
          </button>
        </div>
      )}
    </div>
  );
}

/** Replaces the Run Gemini button while enrichment is in flight - the button
 * disappearing with no feedback read as broken (see #528). Shimmer style
 * matches the intake console's in-flight treatment (`.ownix-shimmer`). */
export function EnrichmentStatusCard() {
  return (
    <section className="rounded-lg border border-line bg-surface p-4">
      <span className="ownix-shimmer font-mono text-sm text-body">
        Gemini is enriching…
      </span>
    </section>
  );
}

/** Trigger button lives in JobActionsBar now (stacked under Copy all); this
 * panel just owns the recipe picker itself - the mobile accordion and the
 * desktop slide panel - driven by state lifted to JobDetailPage so both can
 * share one `open` toggle. */
export function RunGeminiPanel({
  open,
  setOpen,
  error,
  submit,
}: {
  open: boolean;
  setOpen: (value: boolean) => void;
  error?: string;
  submit: (template: string, freestylePrompt?: string) => Promise<void>;
}) {
  const desktop = useDesktopViewport();
  const { templates } = useTemplateList();

  return (
    <section className="space-y-3">
      {error && (
        <p role="alert" className="text-sm text-status-error">
          {error}
        </p>
      )}
      {!desktop && (
        <div
          aria-hidden={!open}
          inert={!open}
          className={`grid overflow-hidden transition-[grid-template-rows] duration-300 ease-out-quart motion-reduce:transition-none ${open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}`}
        >
          <div
            data-testid="gemini-accordion"
            className={`min-h-0 overflow-hidden rounded-lg border border-line bg-surface p-4 transition-[opacity,transform] duration-300 ease-out-quart motion-reduce:transition-none ${open ? 'translate-y-0 opacity-100' : '-translate-y-2 opacity-0'}`}
          >
            <RecipeChoices onSubmit={submit} disabled={!open} />
          </div>
        </div>
      )}
      {desktop && (
        <aside
          data-testid="gemini-slide-panel"
          aria-label="Gemini recipes"
          aria-hidden={!open}
          inert={!open}
          className={`fixed inset-y-0 right-0 z-40 w-full max-w-sm overflow-y-auto border-l border-line bg-surface p-6 shadow-xl transition-transform duration-200 motion-reduce:transition-none ${open ? 'translate-x-0' : 'translate-x-full pointer-events-none'}`}
        >
          <div className="mb-5 flex items-center justify-between">
            <h2 className="text-title font-semibold text-ink">
              Choose a recipe
            </h2>
            <button
              type="button"
              disabled={!open}
              onClick={() => setOpen(false)}
              className="text-sm text-body hover:text-ink"
            >
              Close
            </button>
          </div>
          <RecipeChoices
            disabled={!open}
            onSubmit={submit}
            descriptions={Object.fromEntries(
              templates
                .filter((template) => template.is_builtin)
                .map((template) => [template.name, template.description]),
            )}
          />
        </aside>
      )}
    </section>
  );
}
