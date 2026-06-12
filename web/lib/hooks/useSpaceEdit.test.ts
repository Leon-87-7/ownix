// @vitest-environment jsdom
import { renderHook, waitFor, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useSpaceEdit } from './useSpaceEdit';
import type { SpaceDetail } from './useSpaceDetail';

afterEach(() => vi.unstubAllGlobals());

const SPACE: SpaceDetail = {
  id: 's1',
  chat_id: 12345,
  name: 'My Space',
  color: '#aabbcc',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

function makeEvent() {
  return { preventDefault: vi.fn() } as unknown as React.FormEvent;
}

describe('useSpaceEdit', () => {
  it('starts not editing', () => {
    const { result } = renderHook(() => useSpaceEdit('s1', SPACE, vi.fn()));
    expect(result.current.editing).toBe(false);
  });

  it('startEdit sets editing=true and pre-fills name/color', () => {
    const { result } = renderHook(() => useSpaceEdit('s1', SPACE, vi.fn()));
    act(() => { result.current.startEdit(); });
    expect(result.current.editing).toBe(true);
    expect(result.current.editName).toBe('My Space');
    expect(result.current.editColor).toBe('#aabbcc');
  });

  it('cancelEdit exits editing and clears error', () => {
    const { result } = renderHook(() => useSpaceEdit('s1', SPACE, vi.fn()));
    act(() => { result.current.startEdit(); });
    act(() => { result.current.cancelEdit(); });
    expect(result.current.editing).toBe(false);
    expect(result.current.editError).toBeNull();
  });

  it('handleEditSave does nothing with blank name', async () => {
    const onSaved = vi.fn();
    const { result } = renderHook(() => useSpaceEdit('s1', SPACE, onSaved));
    act(() => {
      result.current.startEdit();
      result.current.setEditName('   ');
    });

    await act(async () => {
      await result.current.handleEditSave(makeEvent());
    });

    expect(onSaved).not.toHaveBeenCalled();
  });

  it('handleEditSave calls onSaved and exits editing on 200', async () => {
    const updated = { ...SPACE, name: 'New Name' };
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: true, status: 200, json: async () => updated }) as Response));

    const onSaved = vi.fn();
    const { result } = renderHook(() => useSpaceEdit('s1', SPACE, onSaved));
    act(() => {
      result.current.startEdit();
      result.current.setEditName('New Name');
    });

    await act(async () => {
      await result.current.handleEditSave(makeEvent());
    });

    expect(onSaved).toHaveBeenCalledWith(updated);
    expect(result.current.editing).toBe(false);
  });

  it('handleEditSave sets editError on 409', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: false, status: 409, json: async () => ({}) }) as Response));

    const { result } = renderHook(() => useSpaceEdit('s1', SPACE, vi.fn()));
    act(() => { result.current.startEdit(); });

    await act(async () => {
      await result.current.handleEditSave(makeEvent());
    });

    expect(result.current.editError).toMatch(/already exists/i);
    expect(result.current.editing).toBe(true);
  });

  it('handleEditSave sets editError on other fetch failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: false, status: 500, json: async () => ({}) }) as Response));

    const { result } = renderHook(() => useSpaceEdit('s1', SPACE, vi.fn()));
    act(() => { result.current.startEdit(); });

    await act(async () => {
      await result.current.handleEditSave(makeEvent());
    });

    expect(result.current.editError).toBeTruthy();
  });
});
