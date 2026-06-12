// @vitest-environment jsdom
import { renderHook, waitFor, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useCreateSpace } from './useCreateSpace';

afterEach(() => vi.unstubAllGlobals());

function makeEvent() {
  return { preventDefault: vi.fn() } as unknown as React.FormEvent;
}

describe('useCreateSpace', () => {
  it('starts with form hidden', () => {
    const { result } = renderHook(() => useCreateSpace(vi.fn(async () => {})));
    expect(result.current.showForm).toBe(false);
  });

  it('openForm shows form', () => {
    const { result } = renderHook(() => useCreateSpace(vi.fn(async () => {})));
    act(() => { result.current.openForm(); });
    expect(result.current.showForm).toBe(true);
  });

  it('resetForm hides form and clears state', () => {
    const { result } = renderHook(() => useCreateSpace(vi.fn(async () => {})));
    act(() => {
      result.current.openForm();
      result.current.setNewName('test');
    });
    act(() => { result.current.resetForm(); });
    expect(result.current.showForm).toBe(false);
    expect(result.current.newName).toBe('');
  });

  it('handleCreate posts and calls onCreated on success', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: true, status: 201, json: async () => ({ id: 's1', name: 'My Space', color: '#6366f1' }) }) as Response));

    const onCreated = vi.fn(async () => {});
    const { result } = renderHook(() => useCreateSpace(onCreated));

    act(() => {
      result.current.openForm();
      result.current.setNewName('My Space');
    });

    await act(async () => {
      await result.current.handleCreate(makeEvent());
    });

    expect(onCreated).toHaveBeenCalled();
    expect(result.current.showForm).toBe(false);
    expect(result.current.formError).toBeNull();
  });

  it('handleCreate does nothing with blank name', async () => {
    const onCreated = vi.fn(async () => {});
    const { result } = renderHook(() => useCreateSpace(onCreated));

    act(() => { result.current.openForm(); });

    await act(async () => {
      await result.current.handleCreate(makeEvent());
    });

    expect(onCreated).not.toHaveBeenCalled();
  });

  it('handleCreate sets formError on 409', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: false, status: 409, json: async () => ({}) }) as Response));

    const { result } = renderHook(() => useCreateSpace(vi.fn(async () => {})));

    act(() => {
      result.current.openForm();
      result.current.setNewName('Dup Name');
    });

    await act(async () => {
      await result.current.handleCreate(makeEvent());
    });

    expect(result.current.formError).toMatch(/already exists/i);
  });

  it('handleCreate sets formError on other fetch failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: false, status: 500, json: async () => ({}) }) as Response));

    const { result } = renderHook(() => useCreateSpace(vi.fn(async () => {})));

    act(() => {
      result.current.openForm();
      result.current.setNewName('Some Name');
    });

    await act(async () => {
      await result.current.handleCreate(makeEvent());
    });

    expect(result.current.formError).toBeTruthy();
  });
});
