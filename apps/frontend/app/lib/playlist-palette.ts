import type { CSSProperties } from "react"

import {
  COVER_COLOR_RANKING,
  FALLBACK_COVER_COLOR,
} from "~/client/constants.gen"

/** Soft fallback when a playlist has no cover colors yet. */
const FALLBACK = [FALLBACK_COVER_COLOR, "#334155", "#94a3b8"]

export function playlistThemeColors(
  themeColors: string[] | null | undefined,
  coverColors: string[] | null | undefined,
): string[] {
  if (themeColors && themeColors.length > 0) return themeColors
  return coverColors ?? []
}

function parseHex(hex: string): [number, number, number] | null {
  const match = /^#?([0-9a-f]{6})$/i.exec(hex.trim())
  if (!match) return null
  const value = match[1]
  return [
    Number.parseInt(value.slice(0, 2), 16),
    Number.parseInt(value.slice(2, 4), 16),
    Number.parseInt(value.slice(4, 6), 16),
  ]
}

function toHex(r: number, g: number, b: number): string {
  return `#${[r, g, b]
    .map((channel) =>
      Math.max(0, Math.min(255, Math.round(channel)))
        .toString(16)
        .padStart(2, "0"),
    )
    .join("")}`
}

function luminance(r: number, g: number, b: number): number {
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
}

function rgbToHsl(
  r: number,
  g: number,
  b: number,
): [number, number, number] {
  const rr = r / 255
  const gg = g / 255
  const bb = b / 255
  const max = Math.max(rr, gg, bb)
  const min = Math.min(rr, gg, bb)
  const lightness = (max + min) / 2
  if (max === min) return [0, 0, lightness]

  const delta = max - min
  const saturation =
    lightness > 0.5 ? delta / (2 - max - min) : delta / (max + min)
  let hue = 0
  if (max === rr) hue = ((gg - bb) / delta + (gg < bb ? 6 : 0)) / 6
  else if (max === gg) hue = ((bb - rr) / delta + 2) / 6
  else hue = ((rr - gg) / delta + 4) / 6
  return [hue, saturation, lightness]
}

function hueToRgb(p: number, q: number, t: number): number {
  let tt = t
  if (tt < 0) tt += 1
  if (tt > 1) tt -= 1
  if (tt < 1 / 6) return p + (q - p) * 6 * tt
  if (tt < 1 / 2) return q
  if (tt < 2 / 3) return p + (q - p) * (2 / 3 - tt) * 6
  return p
}

function hslToRgb(
  h: number,
  s: number,
  l: number,
): [number, number, number] {
  if (s === 0) {
    const gray = l * 255
    return [gray, gray, gray]
  }
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s
  const p = 2 * l - q
  return [
    hueToRgb(p, q, h + 1 / 3) * 255,
    hueToRgb(p, q, h) * 255,
    hueToRgb(p, q, h - 1 / 3) * 255,
  ]
}

/** Lift dark / muddy cover samples into a readable card surface. */
function forCard(hex: string, role: "primary" | "mid" | "deep"): string {
  const rgb = parseHex(hex)
  if (!rgb) return hex
  let [h, s, l] = rgbToHsl(rgb[0], rgb[1], rgb[2])

  // Near-neutral covers still need a hue to complement against.
  if (s < 0.12) {
    s = 0.28
    if (l < 0.2) h = (h + 0.05) % 1
  } else {
    s = Math.min(0.78, Math.max(0.28, s * 1.15))
  }

  if (role === "primary") l = Math.min(0.62, Math.max(0.38, l < 0.35 ? 0.46 : l * 1.15))
  else if (role === "mid") l = Math.min(0.58, Math.max(0.32, l < 0.35 ? 0.4 : l))
  else l = Math.min(0.42, Math.max(0.22, l < 0.35 ? 0.28 : l * 0.85))

  const [r, g, b] = hslToRgb(h, s, l)
  return toHex(r, g, b)
}

function shiftHue(hex: string, delta: number): string {
  const rgb = parseHex(hex)
  if (!rgb) return hex
  const [h, s, l] = rgbToHsl(rgb[0], rgb[1], rgb[2])
  const [r, g, b] = hslToRgb((h + delta) % 1, Math.max(0.28, s), l)
  return toHex(r, g, b)
}

export type PlaylistCardPalette = {
  colors: [string, string, string]
  onDark: boolean
  style: CSSProperties
}

/**
 * Build a 3-stop complementary gradient from ranked cover colors.
 * One seed → primary + complementary + deep shade.
 * Several seeds → ranked colors, gently retuned for card surfaces.
 */
export function playlistCardPalette(
  coverColors: string[] | null | undefined,
): PlaylistCardPalette {
  const seeds = (coverColors ?? [])
    .map((color) => color.trim())
    .filter((color) => parseHex(color))

  const base = seeds.length > 0 ? seeds : FALLBACK
  let c1: string
  let c2: string
  let c3: string

  if (base.length === 1) {
    const seed = base[0]!
    c1 = forCard(seed, "primary")
    c2 = forCard(shiftHue(seed, 0.5), "mid")
    c3 = forCard(seed, "deep")
  } else if (base.length === 2) {
    c1 = forCard(base[0]!, "primary")
    c2 = forCard(base[1]!, "mid")
    c3 = forCard(shiftHue(base[0]!, 0.5), "deep")
  } else {
    c1 = forCard(base[0]!, "primary")
    c2 = forCard(base[1]!, "mid")
    // Prefer a complementary of the top color over a third near-identical dark
    const third = base[2]!
    const rgb = parseHex(third)
    const sat = rgb ? rgbToHsl(rgb[0], rgb[1], rgb[2])[1] : 0
    c3 =
      sat < 0.18
        ? forCard(shiftHue(base[0]!, 0.48), "deep")
        : forCard(third, "deep")
  }

  const samples = [c1, c2, c3]
    .map((hex) => parseHex(hex))
    .filter((rgb): rgb is [number, number, number] => rgb !== null)
  const avg = samples.reduce(
    (acc, [r, g, b]) => ({
      r: acc.r + r / samples.length,
      g: acc.g + g / samples.length,
      b: acc.b + b / samples.length,
    }),
    { r: 0, g: 0, b: 0 },
  )
  const lum = luminance(avg.r, avg.g, avg.b)
  const onDark = lum < 0.58

  return {
    colors: [c1, c2, c3],
    onDark,
    style: {
      backgroundImage: `linear-gradient(135deg, ${c1} 0%, ${c2} 52%, ${c3} 100%)`,
      color: onDark ? "#f8fafc" : "#0f172a",
      ["--playlist-fg-muted" as string]: onDark
        ? "rgba(248, 250, 252, 0.78)"
        : "rgba(15, 23, 42, 0.72)",
      ["--playlist-btn" as string]: onDark
        ? "rgba(248, 250, 252, 0.16)"
        : "rgba(15, 23, 42, 0.08)",
      ["--playlist-btn-hover" as string]: onDark
        ? "rgba(248, 250, 252, 0.28)"
        : "rgba(15, 23, 42, 0.14)",
      ["--playlist-btn-border" as string]: onDark
        ? "rgba(248, 250, 252, 0.42)"
        : "rgba(15, 23, 42, 0.28)",
      ["--playlist-solid" as string]: onDark ? "#f8fafc" : "#0f172a",
      ["--playlist-solid-fg" as string]: onDark ? "#0f172a" : "#f8fafc",
    },
  }
}

function hexChroma(hex: string): number {
  const rgb = parseHex(hex)
  if (!rgb) return 0
  const [r, g, b] = rgb.map((channel) => channel / 255) as [
    number,
    number,
    number,
  ]
  const mx = Math.max(r, g, b)
  const mn = Math.min(r, g, b)
  if (mx <= 1e-6) return 0
  return (mx - mn) / mx
}

/** Rank track cover colors by frequency × chroma (mirrors list API). */
export function rankCoverColors(
  colors: Array<string | null | undefined>,
  limit = COVER_COLOR_RANKING.defaultLimit,
): string[] {
  const counts = new Map<string, number>()
  for (const raw of colors) {
    const color = raw?.trim()
    if (!color || !parseHex(color)) continue
    counts.set(color, (counts.get(color) ?? 0) + 1)
  }
  const bias = COVER_COLOR_RANKING.chromaBias
  return [...counts.entries()]
    .sort((a, b) => {
      const scoreA = a[1] * (bias + hexChroma(a[0]))
      const scoreB = b[1] * (bias + hexChroma(b[0]))
      if (scoreB !== scoreA) return scoreB - scoreA
      const chromaDiff = hexChroma(b[0]) - hexChroma(a[0])
      if (chromaDiff !== 0) return chromaDiff
      return a[0].localeCompare(b[0])
    })
    .slice(0, limit)
    .map(([color]) => color)
}
