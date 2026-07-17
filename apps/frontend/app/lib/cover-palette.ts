export type CoverPalette = {
  /** Dominant colors ranked by presence (up to 6). */
  colors: string[]
  luminance: number
  onDark: boolean
}

const FALLBACK: CoverPalette = {
  colors: ["#334155", "#1e293b", "#0f172a", "#475569", "#64748b", "#0ea5e9"],
  luminance: 0.18,
  onDark: true,
}

const MAX_COLORS = 6

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
    .map((channel) => Math.round(channel).toString(16).padStart(2, "0"))
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

/** Soft caps so player gloss never goes neon or near-black. */
const PLAYER_SAT_MAX = 0.4
const PLAYER_SAT_MIN = 0.08
const PLAYER_LIGHT_MIN = 0.34
const PLAYER_LIGHT_MAX = 0.56

function clampPlayerColor(hex: string): string {
  const rgb = parseHex(hex)
  if (!rgb) return hex
  const [h, s, l] = rgbToHsl(rgb[0], rgb[1], rgb[2])
  const nextS = Math.min(PLAYER_SAT_MAX, Math.max(PLAYER_SAT_MIN, s))
  const nextL = Math.min(PLAYER_LIGHT_MAX, Math.max(PLAYER_LIGHT_MIN, l))
  const [r, g, b] = hslToRgb(h, nextS, nextL)
  return toHex(r, g, b)
}

/** Tone a palette for the floating player (ceil vividness, floor darkness). */
export function softenPlayerPalette(palette: CoverPalette): CoverPalette {
  const colors = palette.colors.map(clampPlayerColor)
  const samples = colors
    .map((hex) => parseHex(hex))
    .filter((rgb): rgb is [number, number, number] => rgb !== null)
  if (samples.length === 0) return palette
  const avg = samples.reduce(
    (acc, [r, g, b]) => ({
      r: acc.r + r / samples.length,
      g: acc.g + g / samples.length,
      b: acc.b + b / samples.length,
    }),
    { r: 0, g: 0, b: 0 },
  )
  const lum = luminance(avg.r, avg.g, avg.b)
  return { colors, luminance: lum, onDark: lum < 0.58 }
}

function quantize(channel: number): number {
  return Math.round(channel / 20) * 20
}

function colorDistance(
  a: { r: number; g: number; b: number },
  b: { r: number; g: number; b: number },
): number {
  const dr = a.r - b.r
  const dg = a.g - b.g
  const db = a.b - b.b
  return Math.sqrt(dr * dr + dg * dg + db * db)
}

/** Pick up to `limit` colors that are both frequent and visually distinct. */
function rankDistinct(
  ranked: { r: number; g: number; b: number; n: number }[],
  limit: number,
): string[] {
  const picked: { r: number; g: number; b: number }[] = []
  for (const sample of ranked) {
    if (picked.length >= limit) break
    const tooClose = picked.some(
      (existing) => colorDistance(existing, sample) < 42,
    )
    if (tooClose) continue
    picked.push(sample)
  }
  // Fill remaining slots from ranked order if diversity filter was too strict.
  for (const sample of ranked) {
    if (picked.length >= limit) break
    if (
      picked.some(
        (existing) =>
          Math.abs(existing.r - sample.r) < 2 &&
          Math.abs(existing.g - sample.g) < 2 &&
          Math.abs(existing.b - sample.b) < 2,
      )
    ) {
      continue
    }
    picked.push(sample)
  }
  while (picked.length < Math.min(3, limit) && ranked[0]) {
    picked.push(ranked[0])
  }
  return picked.map((sample) => toHex(sample.r, sample.g, sample.b))
}

function expandFromSeed(r: number, g: number, b: number): string[] {
  return [
    toHex(r, g, b),
    toHex(r * 0.82, g * 0.82, b * 0.82),
    toHex(r * 0.55, g * 0.55, b * 0.55),
    toHex(Math.min(255, r * 1.15 + 18), Math.min(255, g * 1.05), b * 0.9),
    toHex(r * 0.7, Math.min(255, g * 1.1), Math.min(255, b * 1.2)),
    toHex(Math.min(255, r * 0.95 + 10), g * 0.65, Math.min(255, b * 1.15)),
  ]
}

export function paletteFromHex(hex: string | null | undefined): CoverPalette {
  const rgb = hex ? parseHex(hex) : null
  if (!rgb) return FALLBACK
  const [r, g, b] = rgb
  const lum = luminance(r, g, b)
  return {
    colors: expandFromSeed(r, g, b),
    luminance: lum,
    onDark: lum < 0.58,
  }
}

export async function extractCoverPalette(
  imageUrl: string,
): Promise<CoverPalette> {
  const image = await loadImage(imageUrl)
  const size = 48
  const canvas = document.createElement("canvas")
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext("2d", { willReadFrequently: true })
  if (!ctx) return FALLBACK
  ctx.drawImage(image, 0, 0, size, size)
  const { data } = ctx.getImageData(0, 0, size, size)

  const buckets = new Map<
    string,
    { r: number; g: number; b: number; n: number }
  >()
  for (let i = 0; i < data.length; i += 4) {
    const a = data[i + 3] ?? 0
    if (a < 200) continue
    const r = data[i] ?? 0
    const g = data[i + 1] ?? 0
    const b = data[i + 2] ?? 0
    const lum = luminance(r, g, b)
    if (lum < 0.06 || lum > 0.94) continue
    const max = Math.max(r, g, b)
    const min = Math.min(r, g, b)
    if (max - min < 14) continue
    const key = `${quantize(r)},${quantize(g)},${quantize(b)}`
    const bucket = buckets.get(key)
    if (bucket) {
      bucket.r += r
      bucket.g += g
      bucket.b += b
      bucket.n += 1
    } else {
      buckets.set(key, { r, g, b, n: 1 })
    }
  }

  const ranked = [...buckets.values()]
    .map((bucket) => ({
      r: bucket.r / bucket.n,
      g: bucket.g / bucket.n,
      b: bucket.b / bucket.n,
      n: bucket.n,
    }))
    .sort((a, b) => b.n - a.n)

  if (ranked.length === 0) return FALLBACK

  const colors = rankDistinct(ranked, MAX_COLORS)
  if (colors.length === 0) return FALLBACK
  const seed = colors.slice()
  while (colors.length < MAX_COLORS) {
    colors.push(seed[colors.length % seed.length] ?? FALLBACK.colors[0]!)
  }

  const avg = ranked.slice(0, Math.min(4, ranked.length)).reduce(
    (acc, sample, _, list) => ({
      r: acc.r + sample.r / list.length,
      g: acc.g + sample.g / list.length,
      b: acc.b + sample.b / list.length,
    }),
    { r: 0, g: 0, b: 0 },
  )
  const lum = luminance(avg.r, avg.g, avg.b)
  return { colors, luminance: lum, onDark: lum < 0.58 }
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error("Failed to load cover"))
    image.src = src
  })
}
