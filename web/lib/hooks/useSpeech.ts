'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export function useSpeech(text: string) {
  // ponytail: starts false so server and first client render match; flips
  // true post-mount, avoiding a hydration mismatch on supported browsers.
  const [supported, setSupported] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const speakingRef = useRef(false);
  // ponytail: tracks the in-flight utterance so a stale onend/onerror (fired
  // after cancel() on a queued-but-not-yet-started utterance) can't clobber
  // state for whichever utterance actually replaced it.
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    setSupported(typeof window !== 'undefined' && 'speechSynthesis' in window);
  }, []);

  useEffect(() => {
    return () => {
      if (speakingRef.current) window.speechSynthesis.cancel();
    };
  }, []);

  const toggle = useCallback(() => {
    if (!supported) return;

    const wasSpeaking = speaking;
    window.speechSynthesis.cancel();
    utteranceRef.current = null;
    if (wasSpeaking) {
      speakingRef.current = false;
      setSpeaking(false);
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    const clear = () => {
      if (utteranceRef.current !== utterance) return;
      utteranceRef.current = null;
      speakingRef.current = false;
      setSpeaking(false);
    };
    utterance.onend = clear;
    utterance.onerror = clear;

    // Mark speaking as soon as the utterance is queued, not on onstart:
    // speak() can queue without starting immediately, and a queued utterance
    // still needs to be cancelable (on unmount or a second click).
    utteranceRef.current = utterance;
    speakingRef.current = true;
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }, [speaking, supported, text]);

  return { supported, speaking, toggle };
}
