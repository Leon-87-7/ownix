/** Hands the browser a generated file to save. */
export function downloadMarkdownFile(filename: string, content: string): void {
  const url = URL.createObjectURL(
    new Blob([content], { type: 'text/markdown;charset=utf-8' }),
  );
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  // Revoking synchronously can cancel the download in Firefox — click() queues
  // the fetch of the blob rather than reading it inline. Defer to the next task.
  setTimeout(() => URL.revokeObjectURL(url));
}
