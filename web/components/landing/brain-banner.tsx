import { Brain } from 'lucide-react';

export function BrainBanner() {
  return (
    <div className="mx-auto flex max-w-[960px] items-center justify-center gap-3 border-t border-line p-6">
      <Brain
        aria-hidden="true"
        className="h-6 w-6 shrink-0 text-muted"
      />
      <p className="text-pretty text-button leading-normal">
        <span className="font-medium text-ink">
          You won&apos;t remember the title. Your Brain will.
        </span>
        <br />
        <span className="text-muted">
          Every save joins your Brain - searchable by meaning, not just
          keywords.
        </span>
      </p>
    </div>
  );
}
