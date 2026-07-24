"use client";

import { useEffect, useState } from "react";
import { useGdocExport } from "@/lib/hooks/useGdocExport";
import { SkeletonBlock } from "@/components/feed/feed-states";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

interface ExportModalProps {
  spaceId: string;
  spaceName: string;
  onClose: () => void;
}

export function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  // ponytail: defer — Firefox cancels the download if the URL is revoked synchronously.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function printMarkdown(spaceName: string, markdown: string) {
  const w = window.open("", "_blank");
  if (!w) return;
  const style = w.document.createElement("style");
  style.textContent = "body{font-family:sans-serif;white-space:pre-wrap;padding:2rem}";
  w.document.head.appendChild(style);
  w.document.title = spaceName;
  const pre = w.document.createElement("pre");
  pre.textContent = markdown;
  w.document.body.appendChild(pre);
  w.focus();
  w.print();
}

export default function ExportModal({ spaceId, spaceName, onClose }: ExportModalProps) {
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const { trigger, status: gdocStatus, error: gdocError, errorCode: gdocErrorCode, resultUrl: gdocUrl } = useGdocExport(spaceId);

  const safeName = spaceName.replace(/[/\\:*?"<>|]/g, "_");

  useEffect(() => {
    fetch(`/api/spaces/${spaceId}/export/markdown`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => setMarkdown(d.markdown))
      .catch(() => setLoadError(true));
  }, [spaceId]);

  const handleMd = () => markdown && downloadBlob(markdown, `${safeName}.md`, "text/markdown");
  const handleTxt = () => markdown && downloadBlob(markdown, `${safeName}.txt`, "text/plain");
  const handlePrint = () => markdown && printMarkdown(spaceName, markdown);

  const loading = markdown === null && !loadError;

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
    >
      <DialogContent>
        <DialogTitle>Export &quot;{spaceName}&quot;</DialogTitle>

        <div className="mt-4">
        {loading ? (
          <div className="space-y-3" role="status" aria-label="Composing export">
            <span className="sr-only">Composing export</span>
            <SkeletonBlock className="h-14 w-full" />
            <SkeletonBlock className="h-14 w-full" />
            <SkeletonBlock className="h-14 w-full" />
          </div>
        ) : loadError ? (
          <p className="py-4 text-sm text-status-error">Failed to compose export. Please try again.</p>
        ) : (
          <>
            <p className="mb-5 text-sm text-body">
              Choose a format. Markdown, plain text, and PDF are generated in your browser.
            </p>
            <div className="space-y-3">
              <button onClick={handleMd} className="w-full rounded-lg border border-line bg-canvas px-4 py-3 text-left text-sm text-ink transition-ui hover:border-line-strong hover:bg-raised">
                <span className="font-medium">Download .md</span>
                <span className="ml-2 text-xs text-muted">Markdown file</span>
              </button>
              <button onClick={handleTxt} className="w-full rounded-lg border border-line bg-canvas px-4 py-3 text-left text-sm text-ink transition-ui hover:border-line-strong hover:bg-raised">
                <span className="font-medium">Download .txt</span>
                <span className="ml-2 text-xs text-muted">Plain text file</span>
              </button>
              <button onClick={handlePrint} className="w-full rounded-lg border border-line bg-canvas px-4 py-3 text-left text-sm text-ink transition-ui hover:border-line-strong hover:bg-raised">
                <span className="font-medium">Save as PDF</span>
                <span className="ml-2 text-xs text-muted">Opens browser print dialog</span>
              </button>
              <button onClick={trigger} disabled={gdocStatus === "exporting"} className="w-full rounded-lg border border-line-strong bg-raised px-4 py-3 text-left text-sm text-ink transition-ui hover:border-signal disabled:opacity-50">
                <span className="font-medium">{gdocStatus === "exporting" ? "Creating Google Doc…" : "Create Google Doc"}</span>
                <span className="ml-2 text-xs text-muted">{gdocStatus === "done" ? "Done!" : "Saved to Google Drive · falls back to PDF if Drive unset"}</span>
              </button>
            </div>
            {gdocStatus === "done" && gdocUrl && (
              <p className="mt-4 text-sm text-status-done">
                Google Doc created:{" "}
                <a href={gdocUrl} target="_blank" rel="noopener noreferrer" className="underline transition-ui hover:text-signal">Open</a>
              </p>
            )}
            {gdocStatus === "error" && gdocError && gdocErrorCode === "drive_not_configured" && (
              <div className="mt-4 rounded-lg border border-line bg-canvas p-3">
                <p className="text-sm text-status-error">{gdocError}</p>
                <button onClick={handlePrint} className="mt-3 rounded-md border border-line-strong bg-raised px-3 py-2 text-sm font-medium text-ink transition-ui hover:border-signal">
                  Save as PDF instead
                </button>
              </div>
            )}
            {gdocStatus === "error" && gdocError && gdocErrorCode !== "drive_not_configured" && (
              <p className="mt-4 text-sm text-status-error">{gdocError}</p>
            )}
          </>
        )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
