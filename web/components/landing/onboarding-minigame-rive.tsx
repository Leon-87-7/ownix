'use client';

import { useEffect } from 'react';
import { EventType, Fit, Layout, useRive, useStateMachineInput } from '@rive-app/react-webgl2';

const SRC = '/rive/onboarding-minigame.riv';
const STATE_MACHINE = 'MiniGame';
const END_EVENT = 'end_screen';
const RESTART_INPUT = 'restart';

type Props = {
  active: boolean;
  restartNonce: number;
  onLoad: () => void;
  onEnd: () => void;
  onError: () => void;
};

// Loaded only via next/dynamic from onboarding-minigame.tsx so the Rive
// runtime stays out of the landing page's initial bundle. The contract with
// the .riv file lives in web/public/rive/README.md.
export default function OnboardingMinigameRive({ active, restartNonce, onLoad, onEnd, onError }: Props) {
  const { rive, RiveComponent } = useRive({
    src: SRC,
    stateMachines: STATE_MACHINE,
    autoplay: false,
    layout: new Layout({ fit: Fit.Contain }),
    onLoad,
    onLoadError: onError,
  });

  const restartInput = useStateMachineInput(rive, STATE_MACHINE, RESTART_INPUT);

  useEffect(() => {
    if (!rive) return;
    const handleRiveEvent = (event: { data?: unknown }) => {
      const name = (event.data as { name?: string } | undefined)?.name;
      if (name === END_EVENT) onEnd();
    };
    rive.on(EventType.RiveEvent, handleRiveEvent);
    return () => rive.off(EventType.RiveEvent, handleRiveEvent);
  }, [rive, onEnd]);

  useEffect(() => {
    if (!rive) return;
    if (active) rive.play();
    else rive.pause();
  }, [rive, active]);

  useEffect(() => {
    if (restartNonce > 0) restartInput?.fire();
  }, [restartNonce, restartInput]);

  return <RiveComponent className="h-full w-full" />;
}
