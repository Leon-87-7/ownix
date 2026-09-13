'use client';

import { useMemo, type JSX } from 'react';
import { CopyButton } from '@/components/ui/copy-button';
import { ListenButton } from '@/components/ui/listen-button';
import {
  type RenderType,
  splitPipes,
  humanizeKey,
  isEmpty,
  fieldCopyText,
  parseLinks,
  isSpeakable,
  stripMarkdown,
} from '@/lib/job-markdown';

// --- template_analysis: JSON → readable React tree ---

function JsonValue({ value }: { value: unknown }): JSX.Element | null {
  if (isEmpty(value)) return null;
  if (
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  ) {
    return (
      <p className="whitespace-pre-wrap break-words text-sm text-ink">
        {String(value)}
      </p>
    );
  }
  if (Array.isArray(value)) {
    const allScalar = value.every((v) => typeof v !== 'object' || v === null);
    if (allScalar) {
      return (
        <ul className="list-disc space-y-1 pl-5 text-sm text-ink">
          {value
            .filter((v) => !isEmpty(v))
            .map((v, i) => (
              <li key={i}>{String(v)}</li>
            ))}
        </ul>
      );
    }
    return (
      <ol className="list-decimal space-y-2 pl-5 text-sm text-ink">
        {value.map((v, i) => (
          <li key={i}>
            <JsonValue value={v} />
          </li>
        ))}
      </ol>
    );
  }
  return <JsonObject obj={value as Record<string, unknown>} nested />;
}

function JsonObject({
  obj,
  nested = false,
}: {
  obj: Record<string, unknown>;
  nested?: boolean;
}): JSX.Element | null {
  const entries = Object.entries(obj).filter(([, v]) => !isEmpty(v));
  if (entries.length === 0) return null;
  return (
    <div className={nested ? 'space-y-1' : 'space-y-3'}>
      {entries.map(([key, value]) => {
        const scalar =
          typeof value === 'string' ||
          typeof value === 'number' ||
          typeof value === 'boolean';
        if (nested && scalar) {
          return (
            <p key={key} className="text-sm text-ink">
              <span className="font-medium text-body">
                {humanizeKey(key)}:
              </span>{' '}
              {String(value)}
            </p>
          );
        }
        return (
          <div key={key} className="space-y-1">
            <h3
              className={
                nested
                  ? 'text-xs font-medium text-muted'
                  : 'text-sm font-semibold text-ink'
              }
            >
              {humanizeKey(key)}
            </h3>
            <JsonValue value={value} />
          </div>
        );
      })}
    </div>
  );
}

function TemplateAnalysis({ raw }: { raw: string }) {
  const parsed = useMemo<unknown>(() => {
    try {
      return JSON.parse(raw);
    } catch {
      return undefined;
    }
  }, [raw]);
  if (parsed === undefined) {
    return (
      <p className="whitespace-pre-wrap break-words text-sm text-ink">{raw}</p>
    );
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed))
    return <JsonValue value={parsed} />;
  return <JsonObject obj={parsed as Record<string, unknown>} />;
}

function FieldBody({
  value,
  render,
}: {
  value: string;
  render: RenderType;
}) {
  if (render === 'list') {
    const items = splitPipes(value);
    if (items.length === 0) return <p className="text-sm text-ink">{value}</p>;
    return (
      <ul className="list-disc space-y-1 pl-5 text-sm text-ink">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    );
  }
  if (render === 'links') {
    const links = parseLinks(value);
    if (links.length === 0)
      return (
        <p className="whitespace-pre-wrap break-words text-sm text-ink">
          {value}
        </p>
      );
    return (
      <ul className="space-y-3 text-sm">
        {links.map((link) => {
          const label = link.label || link.url;
          return (
            <li key={link.url} className="space-y-1">
              <a
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="break-all font-medium text-signal transition-ui hover:underline"
              >
                {label}
              </a>
              <p className="break-all font-mono text-xs text-muted">
                {link.url}
              </p>
              {link.description && (
                <p className="whitespace-pre-wrap break-words text-xs text-muted">
                  {link.description}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    );
  }
  if (render === 'json') return <TemplateAnalysis raw={value} />;
  if (render === 'code')
    return (
      <pre className="overflow-x-auto whitespace-pre rounded-md bg-canvas p-3 font-mono text-xs text-ink">
        {value}
      </pre>
    );
  return (
    <p className="whitespace-pre-wrap break-words text-sm text-ink">{value}</p>
  );
}

/** One enrichment field, rendered per its `RenderType`, with listen + copy. */
export function FieldCard({
  label,
  value,
  render,
}: {
  label: string;
  value: string;
  render: RenderType;
}) {
  const speakText = isSpeakable(render)
    ? stripMarkdown(fieldCopyText(value, render))
    : '';
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-mono-label font-medium uppercase tracking-wider text-muted">
          {label}
        </span>
        <div className="flex items-center gap-1.5">
          <ListenButton text={speakText} ariaLabel={`Listen to ${label}`} />
          <CopyButton
            value={fieldCopyText(value, render)}
            ariaLabel={`Copy ${label}`}
          />
        </div>
      </div>
      <FieldBody value={value} render={render} />
    </div>
  );
}
