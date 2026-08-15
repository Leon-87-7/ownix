'use client';

/* @ds
name: IntakeUploadDropzone
purpose: A button-triggered (not drag-and-drop despite the name) file picker for document/image intake — hidden native input, styled trigger button.
when-not: Intake-console-specific. For the richer drag-drop + URL-fetch surface use DocUploadPanel instead.
notes: The accept attribute is only a picker hint — the server content-sniffs the actual bytes, so don't rely on it for validation.
status: inferred
*/

import { useRef, useState, type ChangeEvent } from 'react';
import { FileUp } from 'lucide-react';
import { DOCUMENT_UPLOAD_ACCEPT } from '@/lib/document-formats';

/** Document/image upload for `/intake` (issue #475, multi-format per ADR-0023).
 *  The server content-sniffs the bytes — this `accept` is only a picker hint. */
export function IntakeUploadDropzone({
  onUploaded,
  onError,
}: {
  onUploaded: (file: File) => Promise<void>;
  onError: (message: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const handleChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setUploading(true);
    try {
      await onUploaded(file);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <input
        ref={inputRef}
        type="file"
        accept={DOCUMENT_UPLOAD_ACCEPT}
        onChange={handleChange}
        disabled={uploading}
        className="hidden"
        tabIndex={-1}
        aria-hidden="true"
        id="intake-upload-input"
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        className="flex h-9 items-center gap-2 rounded-md border border-line bg-raised px-3 text-sm font-medium text-body transition-ui hover:border-signal hover:text-ink disabled:opacity-50"
      >
        <FileUp
          className="h-4 w-4"
          aria-hidden="true"
        />
        {uploading ? 'Uploading…' : 'Upload document or image'}
      </button>
    </div>
  );
}
