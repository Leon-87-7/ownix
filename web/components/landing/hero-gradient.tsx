'use client';

import { Component, type ReactNode } from 'react';
import { GrainGradient } from '@paper-design/shaders-react';
import { useReducedMotion } from '@/lib/hooks/useReducedMotion';

// GrainGradient throws when WebGL is unavailable (test/setup.ts mocks it for
// exactly this reason). Without a boundary, that throw has nothing to catch
// it and React unmounts the whole page — so a WebGL-restricted device
// (Safari Private Browsing, Low Power Mode, an old GPU) sees a blank canvas
// instead of just a missing decoration. Fail silent: the scrim + canvas bg
// underneath still reads fine without the shader.
class ShaderBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}

function GrainGradientShader() {
  const reduced = useReducedMotion();

  return (
    <GrainGradient
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 -z-10"
      width="100%"
      height="100%"
      // ponytail: cap the render budget — grain hides the resolution loss,
      // and uncapped retina canvases wedge machines on software WebGL.
      minPixelRatio={1}
      maxPixelCount={1_000_000}
      colors={['#353b45', '#a77735', '#efb667', '#9ecaff', '#649ba0']}
      colorBack="#0e0f11"
      softness={1}
      intensity={0.64}
      noise={0.22}
      shape="corners"
      speed={reduced ? 0 : 1}
      rotation={172}
    />
  );
}

export function HeroGradient() {
  return (
    <ShaderBoundary>
      <GrainGradientShader />
    </ShaderBoundary>
  );
}
