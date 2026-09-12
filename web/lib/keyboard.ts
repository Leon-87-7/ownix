/** Shared guards for window-level keyboard shortcuts.
 *
 * Three call sites grew their own near-identical copy of "is this keystroke
 * mine?" (the job detail pager, FilterBar's `/`, and the global shortcut table
 * in SubmitJobProvider). They are here so a change to what counts as "the user
 * is typing" lands in one place, and so the two genuinely different questions
 * stay named apart rather than drifting into one another. */

/** True when the keystroke belongs to whatever the user is typing into — a form
 * field, a contenteditable, or anything inside a dialog — and so must not be
 * claimed as a global shortcut. */
export function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return (
    tag === 'input' ||
    tag === 'textarea' ||
    tag === 'select' ||
    target.isContentEditable ||
    Boolean(target.closest('[role="dialog"]'))
  );
}

/** True while any dialog is on screen, wherever focus happens to be. Distinct
 * from `isEditableTarget`: a shortcut that *opens* a surface uses this so it
 * can't re-fire behind one that's already open, even when focus sits on body. */
export function hasOpenDialog(): boolean {
  return Array.from(
    document.querySelectorAll<HTMLElement>('[role="dialog"]'),
  ).some(
    (dialog) =>
      dialog.getAttribute('aria-hidden') !== 'true' &&
      dialog.dataset.state !== 'closed',
  );
}

/** The guard for shortcuts that open a surface: skip while the user is typing
 * *or* while any dialog is already up. */
export function shouldIgnoreGlobalShortcut(
  target: EventTarget | null,
): boolean {
  return hasOpenDialog() || isEditableTarget(target);
}
