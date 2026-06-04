'use client'

import { useEffect, useRef } from 'react'

interface MarkdownEditorProps {
  initialMarkdown: string
  onSave: (md: string) => void
}

/**
 * WYSIWYG Markdown editor powered by Milkdown Crepe.
 * Debounces 800 ms after the last keystroke before calling onSave.
 * Cleans up the editor instance on unmount to prevent StrictMode double-init.
 */
export default function MarkdownEditor({ initialMarkdown, onSave }: MarkdownEditorProps) {
  const mountRef = useRef<HTMLDivElement>(null)
  // Keep a stable ref to onSave so the effect closure never goes stale.
  const onSaveRef = useRef(onSave)
  useEffect(() => { onSaveRef.current = onSave }, [onSave])

  useEffect(() => {
    if (!mountRef.current) return

    let crepe: { destroy: () => void } | null = null
    let debounceTimer: ReturnType<typeof setTimeout> | null = null
    let destroyed = false

    async function init() {
      const { Crepe } = await import('@milkdown/crepe')

      if (destroyed || !mountRef.current) return

      const instance = new Crepe({
        root: mountRef.current,
        defaultValue: initialMarkdown,
      })

      // Register the markdown-changed listener via Crepe's .on() helper.
      instance.on((listener) => {
        listener.markdownUpdated((_ctx: unknown, markdown: string) => {
          if (debounceTimer) clearTimeout(debounceTimer)
          debounceTimer = setTimeout(() => {
            onSaveRef.current(markdown)
          }, 800)
        })
      })

      await instance.create()

      if (destroyed) {
        instance.destroy()
        return
      }

      crepe = instance
    }

    init().catch(console.error)

    return () => {
      destroyed = true
      if (debounceTimer) clearTimeout(debounceTimer)
      crepe?.destroy()
    }
    // initialMarkdown intentionally excluded — editor is mounted once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
      <span className="mb-2 block text-xs font-semibold uppercase tracking-wide text-gray-400">
        Notes
      </span>
      <div
        ref={mountRef}
        className="milkdown-editor prose prose-invert max-w-none text-sm text-gray-100 min-h-[6rem]"
      />
    </div>
  )
}
