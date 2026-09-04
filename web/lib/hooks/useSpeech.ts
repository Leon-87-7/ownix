'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAccessibilitySettings } from './useAccessibilitySettings';

// ponytail: module-scoped, shared by every useSpeech instance. Browsers
// don't reliably fire onend/onerror for a queued-but-not-started utterance
// dropped by a global cancel() (e.g. clicking a different listen button),
// so the button that queued it needs an explicit nudge to drop "speaking".
let activeClear: (() => void) | null = null;

export function useSpeech(text: string, voiceURIOverride?: string | null) {
  // ponytail: starts false so server and first client render match; flips
  // true post-mount, avoiding a hydration mismatch on supported browsers.
  const [supported, setSupported] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const speakingRef = useRef(false);
  // ponytail: tracks the in-flight utterance so a stale onend/onerror (fired
  // after cancel() on a queued-but-not-yet-started utterance) can't clobber
  // state for whichever utterance actually replaced it.
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const { voice_uri: persistedVoiceURI } = useAccessibilitySettings();
  const voiceURI = voiceURIOverride !== undefined ? voiceURIOverride : persistedVoiceURI;

  useEffect(() => {
    setSupported(typeof window !== 'undefined' && 'speechSynthesis' in window);
  }, []);

  useEffect(() => {
    return () => {
      // speakingRef only stays true here if nothing else has claimed
      // activeClear since (any other toggle() would have cleared us), so
      // it's safe to drop it unconditionally.
      if (speakingRef.current) {
        window.speechSynthesis.cancel();
        activeClear = null;
      }
    };
  }, []);

  const toggle = useCallback(() => {
    if (!supported) return;

    const wasSpeaking = speaking;
    window.speechSynthesis.cancel();
    activeClear?.();
    activeClear = null;
    utteranceRef.current = null;
    if (wasSpeaking) {
      speakingRef.current = false;
      setSpeaking(false);
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    if (voiceURI) {
      const match = window.speechSynthesis.getVoices().find((v) => v.voiceURI === voiceURI);
      if (match) utterance.voice = match;
    }
    const clear = () => {
      if (utteranceRef.current !== utterance) return;
      utteranceRef.current = null;
      speakingRef.current = false;
      setSpeaking(false);
      if (activeClear === clear) activeClear = null;
    };
    utterance.onend = clear;
    utterance.onerror = clear;

    // Mark speaking as soon as the utterance is queued, not on onstart:
    // speak() can queue without starting immediately, and a queued utterance
    // still needs to be cancelable (on unmount or a second click).
    utteranceRef.current = utterance;
    activeClear = clear;
    speakingRef.current = true;
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }, [speaking, supported, text, voiceURI]);

  return { supported, speaking, toggle };
}
