"use client";

import type { FormEvent } from "react";

const TEMPLATE_OPTIONS = [
  { label: "Method", value: "method" },
  { label: "Review", value: "review" },
  { label: "Technical", value: "technical" },
  { label: "Narrative", value: "narrative" },
  { label: "Summary", value: "summary" },
  { label: "Freestyle", value: "freestyle" },
];

const SELECT_CLASS =
  "h-10 rounded-md border border-line bg-canvas px-3 text-sm text-ink outline-none transition-ui focus:border-signal";

interface SubmitUrlFormProps {
  url: string;
  onUrlChange: (value: string) => void;
  template: string;
  onTemplateChange: (value: string) => void;
  freestylePrompt: string;
  onFreestylePromptChange: (value: string) => void;
  submitting: boolean;
  error: string | null;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}

export function SubmitUrlForm({
  url,
  onUrlChange,
  template,
  onTemplateChange,
  freestylePrompt,
  onFreestylePromptChange,
  submitting,
  error,
  onSubmit,
}: SubmitUrlFormProps) {
  // Matches the search bar's bordered/filled field treatment.
  const urlInputClass =
    "h-10 rounded-md border border-line bg-canvas px-3 text-sm text-ink outline-none transition-ui placeholder:text-muted focus:border-signal";

  return (
    <>
      <form onSubmit={onSubmit} className="grid gap-3">
        <label className="grid gap-1.5 text-sm text-body">
          Submit URL
          <input
            value={url}
            onChange={(event) => onUrlChange(event.target.value)}
            placeholder="Paste a video, article, or repo URL…"
            className={urlInputClass}
          />
        </label>
        <div className="flex items-end gap-3">
          <label className="grid flex-1 gap-1.5 text-sm text-body">
            Template
            <select
              value={template}
              onChange={(event) => onTemplateChange(event.target.value)}
              className={SELECT_CLASS}
            >
              {TEMPLATE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={submitting || !url.trim()}
            className="h-10 shrink-0 rounded-md bg-signal px-4 text-sm font-semibold text-onsignal transition-ui hover:bg-signal-bright active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50 motion-reduce:active:scale-100"
          >
            {submitting ? "Submitting…" : "Submit"}
          </button>
        </div>
        {template === "freestyle" && (
          <label className="grid gap-1.5 text-sm text-body">
            Freestyle prompt
            <textarea
              value={freestylePrompt}
              onChange={(event) => onFreestylePromptChange(event.target.value)}
              placeholder="Tell Gemini exactly how to analyze this job…"
              className="min-h-20 rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink outline-none transition-ui placeholder:text-muted focus:border-signal"
            />
          </label>
        )}
      </form>
      {error && <p className="mt-3 text-sm text-status-error">{error}</p>}
    </>
  );
}
