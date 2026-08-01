import '@testing-library/jest-dom'
import { createElement, type SVGProps } from 'react'
import { vi } from 'vitest'

vi.mock('@/app/ownix-logo.svg', () => ({
  default: (props: SVGProps<SVGSVGElement>) => createElement('svg', props),
}))

// jsdom has no WebGL, so the real shader components throw ("WebGL is not
// supported in this browser") — an async rejection that used to resolve
// quietly but now crashes the run under React 19's effect timing.
vi.mock('@paper-design/shaders-react', () => ({
  PulsingBorder: () => null,
  GrainGradient: () => null,
}))

// jsdom lacks ResizeObserver, which Radix popper-positioned content (e.g. Tooltip) needs.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value:
    window.matchMedia ??
    vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
})
