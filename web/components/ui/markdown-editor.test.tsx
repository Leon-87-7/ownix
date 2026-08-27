// @vitest-environment jsdom
import { render, screen } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
import MarkdownEditor from './markdown-editor';

vi.mock('@milkdown/crepe', () => ({
  Crepe: class {
    on() {}
    async create() {}
    destroy() {}
  },
}));

describe('MarkdownEditor', () => {
  it('reclaims mobile width from Crepe default editor padding', () => {
    render(<MarkdownEditor initialMarkdown="Readable note" onSave={() => {}} />);

    const editor = screen.getByText('Notes').nextElementSibling;

    expect(editor).toHaveClass(
      '[&_.milkdown_.ProseMirror]:pl-14',
      '[&_.milkdown_.ProseMirror]:pr-3',
      '[&_.milkdown_.ProseMirror]:py-4',
      'sm:[&_.milkdown_.ProseMirror]:px-[120px]',
      'sm:[&_.milkdown_.ProseMirror]:py-[60px]',
    );
  });
});
