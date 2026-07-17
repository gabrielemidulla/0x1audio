import { useSyncExternalStore } from "react"

import { trackAudioUrl, type TrackOut } from "~/lib/api"

type Listener = () => void

type PlayerSnapshot = {
  track: TrackOut | null
  playing: boolean
  currentTime: number
  duration: number
  volume: number
}

export type SpectrumBands = {
  bass: number
  mid: number
  treble: number
  energy: number
}

const QUIET_SPECTRUM: SpectrumBands = {
  bass: 0,
  mid: 0,
  treble: 0,
  energy: 0,
}

let audio: HTMLAudioElement | null = null
let track: TrackOut | null = null
let playing = false
let currentTime = 0
let duration = 0
let volume = 1
let audioContext: AudioContext | null = null
let analyser: AnalyserNode | null = null
let mediaSource: MediaElementAudioSourceNode | null = null
let frequencyData: Uint8Array<ArrayBuffer> | null = null
const listeners = new Set<Listener>()
let snapshot: PlayerSnapshot = {
  track: null,
  playing: false,
  currentTime: 0,
  duration: 0,
  volume: 1,
}

function getAudio(): HTMLAudioElement {
  if (!audio) {
    audio = new Audio()
    audio.crossOrigin = "anonymous"
    audio.preload = "metadata"
    audio.volume = volume
    audio.addEventListener("timeupdate", () => {
      currentTime = audio?.currentTime ?? 0
      emit()
    })
    audio.addEventListener("durationchange", () => {
      duration = Number.isFinite(audio?.duration) ? (audio?.duration ?? 0) : 0
      emit()
    })
    audio.addEventListener("play", () => {
      playing = true
      void resumeAudioGraph()
      emit()
    })
    audio.addEventListener("pause", () => {
      playing = false
      emit()
    })
    audio.addEventListener("ended", () => {
      playing = false
      currentTime = 0
      emit()
    })
  }
  return audio
}

function ensureAudioGraph(): AnalyserNode | null {
  if (typeof window === "undefined") return null
  const element = getAudio()
  if (!audioContext) {
    const Context =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext })
        .webkitAudioContext
    if (!Context) return null
    audioContext = new Context()
    analyser = audioContext.createAnalyser()
    analyser.fftSize = 512
    analyser.smoothingTimeConstant = 0.68
    mediaSource = audioContext.createMediaElementSource(element)
    mediaSource.connect(analyser)
    analyser.connect(audioContext.destination)
    frequencyData = new Uint8Array(
      analyser.frequencyBinCount,
    ) as Uint8Array<ArrayBuffer>
  }
  return analyser
}

async function resumeAudioGraph(): Promise<void> {
  ensureAudioGraph()
  if (audioContext?.state === "suspended") {
    try {
      await audioContext.resume()
    } catch {
      // Autoplay / gesture policies can reject; playback still works via element.
    }
  }
}

function bandPeak(data: Uint8Array, from: number, to: number): number {
  let peak = 0
  const end = Math.min(to, data.length)
  const start = Math.max(0, from)
  for (let i = start; i < end; i += 1) {
    const value = data[i] ?? 0
    if (value > peak) peak = value
  }
  return peak / 255
}

function bandAverage(
  data: Uint8Array,
  from: number,
  to: number,
): number {
  let sum = 0
  const end = Math.min(to, data.length)
  const start = Math.max(0, from)
  if (end <= start) return 0
  for (let i = start; i < end; i += 1) sum += data[i] ?? 0
  return sum / ((end - start) * 255)
}

function punch(value: number, gain: number, floor = 0.08): number {
  const shaped = Math.max(0, (value - floor) / (1 - floor))
  return Math.min(1, shaped * gain)
}

/** Live FFT bands in 0–1. Safe to call every animation frame while playing. */
export function readSpectrumBands(): SpectrumBands {
  const node = ensureAudioGraph()
  if (!node || !frequencyData || !playing) return QUIET_SPECTRUM
  node.getByteFrequencyData(frequencyData)
  // fftSize 512 → 256 bins. Sub/kick lives in the first few bins.
  const sub = bandPeak(frequencyData, 1, 4)
  const kick = bandAverage(frequencyData, 1, 8)
  const bass = punch(Math.max(sub * 1.15, kick * 1.05), 1.85, 0.05)
  const mid = punch(bandAverage(frequencyData, 8, 40), 1.25, 0.07)
  const treble = punch(bandAverage(frequencyData, 40, 140), 1.15, 0.06)
  const energy = Math.min(1, bass * 0.7 + mid * 0.2 + treble * 0.1)
  return { bass, mid, treble, energy }
}

function emit() {
  snapshot = { track, playing, currentTime, duration, volume }
  for (const listener of listeners) listener()
}

function subscribe(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function getSnapshot(): PlayerSnapshot {
  return snapshot
}

export function useAudioPlayer() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}

export async function playTrack(next: TrackOut): Promise<void> {
  const element = getAudio()
  ensureAudioGraph()
  const src = trackAudioUrl(next.id)
  const absolute = new URL(src, window.location.origin).href
  if (track?.id !== next.id || element.src !== absolute) {
    track = next
    currentTime = 0
    duration = next.duration_s ?? 0
    element.src = src
    element.load()
    emit()
  } else {
    track = next
    emit()
  }
  await resumeAudioGraph()
  await element.play()
}

export function pauseTrack(): void {
  getAudio().pause()
}

export async function toggleTrack(next: TrackOut): Promise<void> {
  if (track?.id === next.id && playing) {
    pauseTrack()
    return
  }
  await playTrack(next)
}

export function seekTrack(seconds: number): void {
  const element = getAudio()
  if (!Number.isFinite(seconds)) return
  const max = duration || Number.POSITIVE_INFINITY
  element.currentTime = Math.max(0, Math.min(seconds, max))
  currentTime = element.currentTime
  emit()
}

export function setVolume(next: number): void {
  volume = Math.max(0, Math.min(1, next))
  getAudio().volume = volume
  emit()
}

export function closePlayer(): void {
  const element = getAudio()
  element.pause()
  element.removeAttribute("src")
  element.load()
  track = null
  playing = false
  currentTime = 0
  duration = 0
  emit()
}

export function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00"
  const whole = Math.floor(seconds)
  const mins = Math.floor(whole / 60)
  const secs = whole % 60
  return `${mins}:${secs.toString().padStart(2, "0")}`
}
