import { useEffect, useMemo } from "react"
import {
  Color,
  Float32BufferAttribute,
  Mesh,
  MeshBasicMaterial,
  RingGeometry,
  type ColorRepresentation,
} from "three"

import { paletteFromHex } from "~/lib/cover-palette"
import { FALLBACK_COVER_COLOR } from "~/client/constants.gen"

type PaletteRingProps = {
  /** Seed color (usually track.cover_color). */
  color: ColorRepresentation
  /** Reagraph node size — ring scale matches built-in Ring (`size / 2`). */
  size: number
  opacity?: number
}

/** Selection / now-playing ring with a smooth palette gradient around the artwork. */
export function PaletteRing({
  color,
  size,
  opacity = 1,
}: PaletteRingProps) {
  const colors = useMemo(
    () =>
      paletteFromHex(
        typeof color === "string" ? color : FALLBACK_COVER_COLOR,
      ).colors,
    [color],
  )

  const mesh = useMemo(() => {
    // Same proportions as Reagraph Ring(innerRadius=2.3, strokeWidth=1.5).
    const geometry = new RingGeometry(2.22, 2.42, 72)
    const position = geometry.getAttribute("position")
    const stops = colors.slice(0, 4).map((hex) => new Color(hex))
    while (stops.length < 2) stops.push(new Color(FALLBACK_COVER_COLOR))

    const vertexColors = new Float32Array(position.count * 3)
    const mixed = new Color()
    for (let i = 0; i < position.count; i += 1) {
      const x = position.getX(i)
      const y = position.getY(i)
      const angle = (Math.atan2(y, x) + Math.PI) / (Math.PI * 2)
      const scaled = angle * stops.length
      const index = Math.floor(scaled) % stops.length
      const next = (index + 1) % stops.length
      const frac = scaled - Math.floor(scaled)
      mixed.copy(stops[index]!).lerp(stops[next]!, frac)
      vertexColors[i * 3] = mixed.r
      vertexColors[i * 3 + 1] = mixed.g
      vertexColors[i * 3 + 2] = mixed.b
    }
    geometry.setAttribute("color", new Float32BufferAttribute(vertexColors, 3))

    const material = new MeshBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity,
      depthWrite: false,
    })
    const next = new Mesh(geometry, material)
    next.position.set(0, 0, 1)
    // Critical: Reagraph's Ring springs to scale [size/2, size/2, 1], not `size`.
    next.scale.setScalar(size / 2)
    next.frustumCulled = false
    return next
  }, [colors, opacity, size])

  useEffect(() => {
    return () => {
      mesh.geometry.dispose()
      ;(mesh.material as MeshBasicMaterial).dispose()
    }
  }, [mesh])

  return <primitive object={mesh} />
}
