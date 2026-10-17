/**
 * Narration reads captions aloud with a voice on the learner's machine (AN-18).
 *
 * Only voices marked localService are used, so no caption text leaves the
 * machine and narration works offline. With no local voice the player does
 * not offer narration at all. It is off until the learner turns it on, and
 * the choice is remembered in this browser.
 */

import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'polaris.animation.narration'

function synth(): SpeechSynthesis | null {
  if (typeof window === 'undefined') return null
  return window.speechSynthesis ?? null
}

/** The first local voice, preferring one in the page's language. */
export function pickLocalVoice(voices: readonly SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  const local = voices.filter((voice) => voice.localService === true)
  if (local.length === 0) return null
  const language = (document.documentElement.lang || navigator.language || '').toLowerCase()
  const prefix = language.split('-')[0]
  return (
    local.find((voice) => prefix && voice.lang.toLowerCase().startsWith(prefix)) ??
    local.find((voice) => voice.default) ??
    local[0]
  )
}

function readVoice(): SpeechSynthesisVoice | null {
  const speech = synth()
  if (!speech || typeof speech.getVoices !== 'function') return null
  return pickLocalVoice(speech.getVoices())
}

/** The local voice to narrate with, or null. Voices can load late, so it listens for changes. */
export function useLocalVoice(): SpeechSynthesisVoice | null {
  const [voice, setVoice] = useState<SpeechSynthesisVoice | null>(readVoice)
  useEffect(() => {
    const speech = synth()
    if (!speech || typeof speech.addEventListener !== 'function') return
    const update = () => setVoice(readVoice())
    speech.addEventListener('voiceschanged', update)
    return () => speech.removeEventListener('voiceschanged', update)
  }, [])
  return voice
}

function readChoice(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'on'
  } catch {
    return false
  }
}

function saveChoice(on: boolean): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, on ? 'on' : 'off')
  } catch {
    // Storage can be blocked; narration still works for this visit.
  }
}

/** Whether narration is on, remembered between visits. Off by default. */
export function useNarrationChoice(): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(readChoice)
  const change = useCallback((next: boolean) => {
    setOn(next)
    saveChoice(next)
  }, [])
  return [on, change]
}

export function stopSpeaking(): void {
  synth()?.cancel()
}

export function speak(text: string, voice: SpeechSynthesisVoice): void {
  const speech = synth()
  if (!speech || typeof SpeechSynthesisUtterance === 'undefined') return
  speech.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.voice = voice
  utterance.lang = voice.lang
  speech.speak(utterance)
}
