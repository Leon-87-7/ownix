import '@testing-library/jest-dom'

// jsdom lacks ResizeObserver, which Radix popper-positioned content (e.g. Tooltip) needs.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
