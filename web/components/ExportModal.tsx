"use client";

import { useEffect, useState } from "react";

interface ExportModalProps {
  spaceId: string;
  spaceName: string;
  onClose: () => void;
}

type ExportStatus = "idle" | "exporting" | "done" | "error";

function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
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

  const [gdocStatus, setGdocStatus] = useState<ExportStatus>("idle");
  const [gdocUrl, setGdocUrl] = useState<string | null>(null);
  const [gdocError, setGdocError] = useState<string | null>(null);

  const safeName = spaceName.replace(/[/\\:*?"<>|]/g, "_");

  // Fetch composed markdown when the modal opens.
  useEffect(() => {
    fetch(`/api/spaces/${spaceId}/export/markdown`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => setMarkdown(d.markdown))
      .catch(() => setLoadError(true));
  }, [spaceId]);

  const handleMd = () => markdown && downloadBlob(markdown, `${safeName}.md`, "text/markdown");
  const handleTxt = () => markdown && downloadBlob(markdown, `${safeName}.txt`, "text/plain");
  const handlePrint = () => markdown && printMarkdown(spaceName, markdown);

  const handleGdoc = async () => {
    setGdocStatus("exporting");
    setGdocError(null);
    try {
      const res = await fetch(`/api/spaces/${spaceId}/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ format: "gdoc" }),
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        if (data.error === "drive_not_configured") {
          setGdocError("Google Drive is not configured. Use the .md, .txt, or PDF buttons above.");
          setGdocStatus("error");
        } else {
          throw new Error(data.detail || data.error || "Export failed");
        }
        return;
      }
      setGdocUrl(data.url);
      setGdocStatus("done");
    } catch (err) {
      setGdocError(err instanceof Error ? err.message : "Unknown error");
      setGdocStatus("error");
    }
  };

  const loading = markdown === null && !loadError;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-md rounded-xl bg-gray-900 p-6 shadow-2xl border border-gray-700">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-white">Export "{spaceName}"</h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-400 hover:text-white transition-colors"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {loading ? (
          <div className="flex items-center gap-2 py-8 text-sm text-gray-400 justify-center">
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-gray-600 border-t-white" />
            Composing export…
          </div>
        ) : loadError ? (
          <p className="py-4 text-sm text-red-400">Failed to compose export. Please try again.</p>
        ) : (
          <>
        <p className="mb-5 text-sm text-gray-400">
          Choose a format. Markdown, plain text, and PDF are generated in your browser.
        </p>

        <div className="space-y-3">
          {/* Markdown */}
          <button
            onClick={handleMd}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-left text-sm text-gray-100 hover:border-indigo-500 hover:bg-gray-750 transition-colors"
          >
            <span className="font-medium">Download .md</span>
            <span className="ml-2 text-xs text-gray-400">Markdown file</span>
          </button>

          {/* Plain text */}
          <button
            onClick={handleTxt}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-left text-sm text-gray-100 hover:border-indigo-500 transition-colors"
          >
            <span className="font-medium">Download .txt</span>
            <span className="ml-2 text-xs text-gray-400">Plain text file</span>
          </button>

          {/* PDF (print) */}
          <button
            onClick={handlePrint}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-3 text-left text-sm text-gray-100 hover:border-indigo-500 transition-colors"
          >
            <span className="font-medium">Save as PDF</span>
            <span className="ml-2 text-xs text-gray-400">Opens browser print dialog</span>
          </button>

          {/* Google Doc */}
          <button
            onClick={handleGdoc}
            disabled={gdocStatus === "exporting"}
            className="w-full rounded-lg border border-indigo-700 bg-indigo-900/40 px-4 py-3 text-left text-sm text-indigo-200 hover:border-indigo-500 disabled:opacity-50 transition-colors"
          >
            <span className="font-medium">
              {gdocStatus === "exporting" ? "Creating Google Doc…" : "Create Google Doc"}
            </span>
            <span className="ml-2 text-xs text-indigo-400">
              {gdocStatus === "done"
                ? "Done!"
                : "Saved to Google Drive · falls back to PDF if Drive unset"}
            </span>
          </button>
        </div>

        {gdocStatus === "done" && gdocUrl && (
          <p className="mt-4 text-sm text-green-400">
            Google Doc created:{" "}
            <a
              href={gdocUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-green-300"
            >
              Open
            </a>
          </p>
        )}

        {gdocStatus === "error" && gdocError && (
          <p className="mt-4 text-sm text-red-400">{gdocError}</p>
        )}
          </>
        )}
      </div>
    </div>
  );
}
