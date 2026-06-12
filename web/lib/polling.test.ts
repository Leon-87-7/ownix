// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { startPolling } from './polling';

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); });

describe('startPolling tick', () => {
  it('calls fetchFn after the interval', async () => {
    const fetchFn = vi.fn(async () => {});
    const isIdleFn = vi.fn(() => false);

    startPolling(fetchFn, isIdleFn, 1000);

    expect(fetchFn).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1000);
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it('stops polling when isIdleFn returns true', async () => {
    const fetchFn = vi.fn(async () => {});
    let idle = false;
    const isIdleFn = vi.fn(() => idle);

    startPolling(fetchFn, isIdleFn, 1000);

    await vi.advanceTimersByTimeAsync(1000);
    expect(fetchFn).toHaveBeenCalledTimes(1);

    idle = true;
    await vi.advanceTimersByTimeAsync(1000);
    // Should not fire again because idle
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it('stops when cancel function is called', async () => {
    const fetchFn = vi.fn(async () => {});
    const isIdleFn = vi.fn(() => false);

    const cancel = startPolling(fetchFn, isIdleFn, 1000);
    cancel();

    await vi.advanceTimersByTimeAsync(5000);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it('swallows fetch errors and continues', async () => {
    let callCount = 0;
    const fetchFn = vi.fn(async () => {
      callCount++;
      if (callCount === 1) throw new Error('Network error');
    });
    const isIdleFn = vi.fn(() => callCount >= 2);

    startPolling(fetchFn, isIdleFn, 1000);

    await vi.advanceTimersByTimeAsync(1000);
    expect(fetchFn).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(1000);
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it('does not fire if isIdleFn is immediately true', async () => {
    const fetchFn = vi.fn(async () => {});
    const isIdleFn = vi.fn(() => true);

    startPolling(fetchFn, isIdleFn, 1000);

    await vi.advanceTimersByTimeAsync(3000);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it('schedules repeated ticks while not idle', async () => {
    const fetchFn = vi.fn(async () => {});
    let callCount = 0;
    const isIdleFn = vi.fn(() => { callCount = (fetchFn.mock.calls.length); return callCount >= 3; });

    startPolling(fetchFn, isIdleFn, 500);

    await vi.advanceTimersByTimeAsync(2000);
    expect(fetchFn.mock.calls.length).toBeGreaterThanOrEqual(3);
  });
});
