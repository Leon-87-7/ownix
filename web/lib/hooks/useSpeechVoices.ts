'use client';

import { useEffect, useState } from 'react';

export function useSpeechVoices() {
  const [supported, setSupported] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);

  useEffect(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    setSupported(true);
    const update = () => setVoices(window.speechSynthesis.getVoices());
    update();
    window.speechSynthesis.addEventListener('voiceschanged', update);
    return () => window.speechSynthesis.removeEventListener('voiceschanged', update);
  }, []);

  return { supported, voices };
}

export interface VoiceLanguageGroup {
  lang: string;
  label: string;
  voices: SpeechSynthesisVoice[];
}

// Intl.DisplayNames#of() throws RangeError on a malformed BCP-47 tag (verified:
// `new Intl.DisplayNames(['en'], {type:'language'}).of('not-a-real-lang-tag')`
// throws rather than returning a fallback) — a real browser's voice.lang
// should always be well-formed, but a label helper for OS-provided strings
// shouldn't be able to crash the whole picker over one malformed one.
function languageLabel(lang: string, displayNames: Intl.DisplayNames | null): string {
  try {
    return displayNames?.of(lang) ?? lang;
  } catch {
    return lang;
  }
}

export function groupVoicesByLanguage(voices: SpeechSynthesisVoice[]): VoiceLanguageGroup[] {
  const byLang = new Map<string, SpeechSynthesisVoice[]>();
  for (const v of voices) {
    const list = byLang.get(v.lang) ?? [];
    list.push(v);
    byLang.set(v.lang, list);
  }
  const displayNames =
    typeof Intl !== 'undefined' && 'DisplayNames' in Intl
      ? new Intl.DisplayNames(['en'], { type: 'language' })
      : null;
  return Array.from(byLang.entries())
    .map(([lang, list]) => ({
      lang,
      label: languageLabel(lang, displayNames),
      voices: [...list].sort((a, b) => a.name.localeCompare(b.name)),
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
}
