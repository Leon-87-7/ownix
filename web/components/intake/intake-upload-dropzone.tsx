'use client';

import { useRef, useState, type ChangeEvent } from 'react';
import { FileUp } from 'lucide-react';

/** PDF/image upload for `/intake` (issue #475). Server sniffs content, not this input's `accept`. */
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
        accept="application/pdf,image/*"
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
        {uploading ? 'Uploading…' : 'Upload PDF or image'}
      </button>
    </div>
  );
}
