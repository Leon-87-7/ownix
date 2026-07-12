// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useJobTags } from './useJobTags';

describe('useJobTags', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('does not throw or fetch when createTag is disabled', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useJobTags('job-1', 'ok', true));

    await act(() =>
      result.current.createTag({
        name: 'restricted',
        meaning: '',
        color: '#6366f1',
      }),
    );

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
