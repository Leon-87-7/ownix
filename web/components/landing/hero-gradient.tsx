'use client';

import { GrainGradient } from '@paper-design/shaders-react';
import { useReducedMotion } from '@/lib/hooks/useReducedMotion';

export function HeroGradient() {
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
