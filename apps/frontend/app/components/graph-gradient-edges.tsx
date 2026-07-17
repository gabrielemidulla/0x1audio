import { useEffect, useMemo, type MutableRefObject } from "react"
import {
  Color,
  Float32BufferAttribute,
  Mesh,
  MeshBasicMaterial,
  QuadraticBezierCurve3,
  TubeGeometry,
  Vector3,
} from "three"

type Point = { x: number; y: number }

export type GradientEdgeInput = {
  id: string
  source: string
  target: string
  size: number
  sourceColor: string
  targetColor: string
}

type GraphGradientEdgesProps = {
  edges: GradientEdgeInput[]
  positionsRef: MutableRefObject<Map<string, Point>>
  sizeById: Map<string, number>
  actives: string[]
  layoutVersion: number
}

function offsetPoint(from: Vector3, to: Vector3, distance: number): Vector3 {
  const direction = new Vector3().subVectors(to, from)
  const length = direction.length()
  if (length < 1e-6) return from.clone()
  return from.clone().addScaledVector(direction.normalize(), Math.min(distance, length * 0.45))
}

function curveControl(from: Vector3, to: Vector3): Vector3 {
  const mid = new Vector3().addVectors(from, to).multiplyScalar(0.5)
  const direction = new Vector3().subVectors(to, from)
  const perpendicular = new Vector3(-direction.y, direction.x, 0).normalize()
  const lift = Math.min(80, direction.length() * 0.18)
  return mid.addScaledVector(perpendicular, lift)
}

function buildTube(
  from: Point,
  to: Point,
  fromSize: number,
  toSize: number,
  radius: number,
  sourceColor: string,
  targetColor: string,
): TubeGeometry {
  const start = new Vector3(from.x, from.y, 0)
  const end = new Vector3(to.x, to.y, 0)
  const fromPoint = offsetPoint(start, end, fromSize)
  const toPoint = offsetPoint(end, start, toSize)
  const curve = new QuadraticBezierCurve3(
    fromPoint,
    curveControl(fromPoint, toPoint),
    toPoint,
  )
  const tubularSegments = 40
  const radialSegments = 6
  const geometry = new TubeGeometry(
    curve,
    tubularSegments,
    radius,
    radialSegments,
    false,
  )
  const position = geometry.getAttribute("position")
  const colorStart = new Color(sourceColor)
  const colorEnd = new Color(targetColor)
  const mixed = new Color()
  const vertexColors = new Float32Array(position.count * 3)
  const stride = radialSegments + 1

  for (let i = 0; i < position.count; i += 1) {
    const tubeIndex = Math.floor(i / stride)
    const t = tubeIndex / tubularSegments
    mixed.copy(colorStart).lerp(colorEnd, t)
    vertexColors[i * 3] = mixed.r
    vertexColors[i * 3 + 1] = mixed.g
    vertexColors[i * 3 + 2] = mixed.b
  }
  geometry.setAttribute("color", new Float32BufferAttribute(vertexColors, 3))
  return geometry
}

function GradientEdgeMesh({
  edge,
  positionsRef,
  sizeById,
  emphasized,
  layoutVersion,
}: {
  edge: GradientEdgeInput
  positionsRef: MutableRefObject<Map<string, Point>>
  sizeById: Map<string, number>
  emphasized: boolean
  layoutVersion: number
}) {
  const mesh = useMemo(() => {
    const from = positionsRef.current.get(edge.source)
    const to = positionsRef.current.get(edge.target)
    if (!from || !to) return null
    const geometry = buildTube(
      from,
      to,
      sizeById.get(edge.source) ?? 24,
      sizeById.get(edge.target) ?? 24,
      Math.max(0.28, edge.size * 0.4),
      edge.sourceColor,
      edge.targetColor,
    )
    const material = new MeshBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.92,
      depthWrite: false,
    })
    const next = new Mesh(geometry, material)
    next.frustumCulled = false
    next.renderOrder = -1
    return next
    // positions snap only when layoutVersion bumps
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [edge, sizeById, layoutVersion, positionsRef])

  useEffect(() => {
    if (!mesh) return
    const material = mesh.material as MeshBasicMaterial
    material.opacity = emphasized ? 0.92 : 0.12
    material.needsUpdate = true
  }, [emphasized, mesh])

  useEffect(() => {
    return () => {
      if (!mesh) return
      mesh.geometry.dispose()
      ;(mesh.material as MeshBasicMaterial).dispose()
    }
  }, [mesh])

  if (!mesh) return null
  return <primitive object={mesh} />
}

/** Curved tubes colored as a gradient from node A → node B cover colors. */
export function GraphGradientEdges({
  edges,
  positionsRef,
  sizeById,
  actives,
  layoutVersion,
}: GraphGradientEdgesProps) {
  const activeSet = useMemo(() => new Set(actives), [actives])
  const hasFocus = activeSet.size > 0

  return (
    <group>
      {edges.map((edge) => {
        const emphasized =
          !hasFocus ||
          activeSet.has(edge.id) ||
          activeSet.has(edge.source) ||
          activeSet.has(edge.target)
        return (
          <GradientEdgeMesh
            key={`${edge.id}:${layoutVersion}`}
            edge={edge}
            positionsRef={positionsRef}
            sizeById={sizeById}
            emphasized={emphasized}
            layoutVersion={layoutVersion}
          />
        )
      })}
    </group>
  )
}
