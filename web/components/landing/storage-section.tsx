import { GoogleDriveIcon } from '@/components/svg/google-drive-icon';

export function StorageSection() {
  return (
    <section
      aria-labelledby="No-lock-in-storage"
      className="border-t border-line bg-canvas-gradient py-12 sm:bg-canvas"
    >
      <div className="mx-auto max-w-[960px] px-6">
        <h2
          id="No-lock-in-storage"
          className="mb-4 font-title text-[clamp(1.375rem,3.4vw,1.75rem)] font-semibold leading-tight tracking-[-0.25px] text-ink"
        >
          {' '}
          No lock-in storage
        </h2>
        <p className="text-pretty mb-6 max-w-[58ch] text-prose leading-relaxed">
          If Ownix vanished tomorrow, your stuff wouldn&apos;t.
          Everything also lands in your Google Drive as markdown - plug
          in Claude&apos;s or ChatGPT&apos;s{' '}
          <span className="underline-offset-2 underline decoration-dotted decoration-contrasignal">
            Drive connector
          </span>
          &ensp;and your AI reads your whole Index directly. No export,
          no copy-paste.
        </p>

        <p className="text-pretty mb-6 max-w-[58ch] text-prose leading-relaxed ml-4 mt-3 font-mono text-xs text-muted">
          Google Drive is where it lives today - more storage endpoints
          are on the roadmap.
        </p>

        <div className="flex mb-6 mx-auto max-w-[58ch] items-center justify-center gap-3 rounded-lg border border-line bg-surface p-4">
          <GoogleDriveIcon className="h-6 w-6 shrink-0" />
          <div className="flex flex-col items-center">
            <b className="font-subtitle font-medium text-ink">
              Your files, your account, your storage{' '}
            </b>
            <span className="font-title font-normal">
              leave anytime and lose nothing.
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
