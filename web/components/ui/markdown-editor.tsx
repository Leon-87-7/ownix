'use client'

import { useEffect, useRef } from 'react'

// Crepe ships its editor chrome (toolbar, slash-menu, placeholder, list/table
// styling) entirely via CSS. Without these imports the WYSIWYG controls render
// unstyled or invisible, so a non-technical user never sees the formatting UI.
// `common` is the required base; `frame-dark` matches the dark dashboard theme.
import '@milkdown/crepe/theme/common/style.css'
import '@milkdown/crepe/theme/frame-dark.css'

interface MarkdownEditorProps {
  initialMarkdown: string
  onSave?: (md: string) => void
  label?: string
  /** Renders the same Crepe/remark output with editing chrome (toolbar, slash
   * menu, block handles) and typing disabled — for display-only surfaces that
   * still want correct markdown rendering. Also drops the wide desktop
   * editing padding, which reads as broken word-wrap in a narrow column. */
  readOnly?: boolean
}

/**
 * WYSIWYG Markdown editor powered by Milkdown Crepe.
 * Debounces 800 ms after the last keystroke before calling onSave.
 * Cleans up the editor instance on unmount to prevent StrictMode double-init.
 */
export default function MarkdownEditor({
  initialMarkdown,
  onSave,
  label = 'Notes',
  readOnly = false,
}: MarkdownEditorProps) {
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
        features: readOnly
          ? {
              [Crepe.Feature.Toolbar]: false,
              [Crepe.Feature.BlockEdit]: false,
              [Crepe.Feature.LinkTooltip]: false,
              [Crepe.Feature.Placeholder]: false,
            }
          : undefined,
      })

      if (!readOnly) {
        // Register the markdown-changed listener via Crepe's .on() helper.
        instance.on((listener) => {
          listener.markdownUpdated((_ctx: unknown, markdown: string) => {
            if (debounceTimer) clearTimeout(debounceTimer)
            debounceTimer = setTimeout(() => {
              onSaveRef.current?.(markdown)
            }, 800)
          })
        })
      }

      await instance.create()

      if (destroyed) {
        instance.destroy()
        return
      }

      if (readOnly) instance.setReadonly(true)
      crepe = instance
    }

    init().catch(console.error)

    return () => {
      destroyed = true
      if (debounceTimer) clearTimeout(debounceTimer)
      crepe?.destroy()
    }
    // initialMarkdown/readOnly intentionally excluded — editor is mounted once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className={readOnly ? 'min-w-0' : 'rounded-lg border border-line bg-surface p-2 sm:p-4'}>
      {label && (
        <span className="mb-2 block font-mono text-mono-label font-medium uppercase tracking-wider text-muted">
          {label}
        </span>
      )}
      <div
        ref={mountRef}
        className={
          readOnly
            ? 'milkdown-editor prose prose-invert min-w-0 max-w-none text-sm text-body [&_.milkdown_.ProseMirror]:p-0'
            : 'milkdown-editor prose prose-invert min-h-[6rem] max-w-none text-sm text-ink [&_.milkdown_.ProseMirror]:py-4 [&_.milkdown_.ProseMirror]:pl-14 [&_.milkdown_.ProseMirror]:pr-3 sm:[&_.milkdown_.ProseMirror]:px-[120px] sm:[&_.milkdown_.ProseMirror]:py-[60px]'
        }
      />
    </div>
  )
}
