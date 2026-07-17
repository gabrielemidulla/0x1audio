import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useSearchParams } from "react-router"
import {
  Crosshair,
  Graph,
  MagnifyingGlassMinus,
  MagnifyingGlassPlus,
  MusicNote,
  Pause,
  Play,
} from "@phosphor-icons/react"
import {
  GraphCanvas,
  Icon,
  Label as NodeLabel,
  Sphere,
  type GraphCanvasRef,
  type GraphEdge,
  type GraphNode,
  type LayoutOverrides,
  type NodePositionArgs,
  type NodeRendererProps,
  type Theme,
} from "reagraph"
import type {} from "@react-three/fiber"

import {
  api,
  trackCoverUrl,
  type GraphLinkOut,
  type GraphResponseOut,
  type TrackOut,
} from "~/lib/api"
import { playTrack, toggleTrack, useAudioPlayer } from "~/lib/audio-player"
import {
  GraphGradientEdges,
  type GradientEdgeInput,
} from "~/components/graph-gradient-edges"
import { PaletteRing } from "~/components/graph-palette-ring"
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "~/components/ui/combobox"
import { Button } from "~/components/ui/button"
import { Label } from "~/components/ui/label"

const DEFAULT_LIMIT = 24
const FALLBACK_COLOR = "#64748b"
const SEED_LIMIT = 20
const SEED_DEBOUNCE_MS = 300
// Bundled Figtree (same family as app CSS) — troika needs a .ttf/.woff URL.
const GRAPH_FONT_URL = "/fonts/figtree-latin-400-normal.ttf"

// App slate neutrals. Built-in edge strokes are hidden; we draw gradient tubes.
const graphTheme: Theme = {
  canvas: { background: "#fafafa" },
  node: {
    fill: "#94a3b8",
    activeFill: "#0f172a",
    opacity: 1,
    selectedOpacity: 1,
    inactiveOpacity: 0.15,
    label: {
      color: "#0f172a",
      stroke: "#fafafa",
      activeColor: "#0f172a",
    },
    subLabel: {
      color: "#64748b",
      stroke: "#fafafa",
      activeColor: "#475569",
    },
  },
  ring: { fill: "#e2e8f0", activeFill: "#64748b" },
  edge: {
    fill: "#000000",
    activeFill: "#000000",
    opacity: 0,
    selectedOpacity: 0,
    inactiveOpacity: 0,
    label: {
      color: "#64748b",
      stroke: "#fafafa",
      activeColor: "#0f172a",
      fontSize: 6,
    },
  },
  arrow: { fill: "#cbd5e1", activeFill: "#64748b" },
  lasso: {
    border: "1px solid #64748b",
    background: "rgba(100, 116, 139, 0.12)",
  },
}

type GraphLink = GraphLinkOut & { id: string }

function edgeKey(a: string, b: string): string {
  return a < b ? `${a}|${b}` : `${b}|${a}`
}

function coverUrl(trackId: string): string {
  return trackCoverUrl(trackId)
}

function edgeSize(weight: number): number {
  return Math.max(0.3, Math.min(1, weight))
}

const MIN_NODE_SIZE = 24
const MAX_NODE_SIZE = 32

// Size must not depend on the focused node: Reagraph re-runs the whole
// force layout when node attributes change, so focus emphasis comes from
// the selection ring instead. Sizes only differ between expanded nodes
// and their frontier, which already changes membership (and relayouts).
function nodeSize(id: string, expandedIds: Set<string>): number {
  return expandedIds.has(id) ? MAX_NODE_SIZE : MIN_NODE_SIZE
}

const TITLE_FONT_SIZE = 11
const ARTIST_FONT_SIZE = 8

type Point = { x: number; y: number }

const RING_RADIUS = 220
const RING_SPREAD = 160
const RING_STAGGER = 36
// Extra space for title (+ optional artist) under neighboring covers.
const MIN_SEPARATION = MAX_NODE_SIZE * 2 + 160
// Tight framing: fit the focus and its closest ring, letting weaker
// neighbors fall toward the edges instead of zooming out for them.
const FRAME_RADIUS = RING_RADIUS + RING_SPREAD / 2 + 40

// Deterministic layout (ported from the goodtaste explorer): new neighbors
// land on a ring around the node being expanded, ordered by similarity so
// the closest tracks sit nearest. Already-placed nodes never move, which
// keeps the map stable across expansions.
function placeNeighborhood(
  positions: Map<string, Point>,
  centerId: string,
  graph: GraphResponseOut,
) {
  const center = positions.get(centerId) ?? { x: 0, y: 0 }
  positions.set(centerId, center)

  const weightById = new Map<string, number>()
  for (const link of graph.links) {
    if (link.source === centerId) weightById.set(link.target, link.weight)
    if (link.target === centerId) weightById.set(link.source, link.weight)
  }

  const newcomers = graph.nodes
    .map((node) => node.track.id)
    .filter((id) => id !== centerId && !positions.has(id))
    .sort((a, b) => (weightById.get(b) ?? 0) - (weightById.get(a) ?? 0))

  const angleOffset = (positions.size % 7) * 0.9
  newcomers.forEach((id, index) => {
    const angle =
      angleOffset + (index / Math.max(newcomers.length, 1)) * Math.PI * 2
    const weight = weightById.get(id) ?? 0.56
    const closeness = Math.max(0, Math.min(1, (weight - 0.56) / 0.44))
    const distance =
      RING_RADIUS + (1 - closeness) * RING_SPREAD + (index % 4) * RING_STAGGER
    positions.set(id, {
      x: center.x + Math.cos(angle) * distance,
      y: center.y + Math.sin(angle) * distance,
    })
  })

  relaxNewcomers(positions, new Set(newcomers))
}

// Push overlapping newcomers apart; nodes placed in earlier expansions stay put.
function relaxNewcomers(positions: Map<string, Point>, newcomers: Set<string>) {
  const entries = [...positions.entries()]
  for (let pass = 0; pass < 8; pass += 1) {
    for (let i = 0; i < entries.length; i += 1) {
      for (let j = i + 1; j < entries.length; j += 1) {
        const [leftId, left] = entries[i]
        const [rightId, right] = entries[j]
        const leftMovable = newcomers.has(leftId)
        const rightMovable = newcomers.has(rightId)
        if (!leftMovable && !rightMovable) continue

        const dx = right.x - left.x
        const dy = right.y - left.y
        const distance = Math.max(Math.hypot(dx, dy), 1)
        if (distance >= MIN_SEPARATION) continue

        const push = MIN_SEPARATION - distance
        const unitX = dx / distance
        const unitY = dy / distance
        if (leftMovable && rightMovable) {
          left.x -= (unitX * push) / 2
          left.y -= (unitY * push) / 2
          right.x += (unitX * push) / 2
          right.y += (unitY * push) / 2
        } else if (leftMovable) {
          left.x -= unitX * push
          left.y -= unitY * push
        } else {
          right.x += unitX * push
          right.y += unitY * push
        }
      }
    }
  }
}

// Reagraph's built-in labels have a hardcoded font size, so the node
// renderer draws its own: cover art (or sphere) plus title and artist.
const renderTrackNode = (props: NodeRendererProps) => <TrackNode {...props} />

function TrackNode({ node, ...rest }: NodeRendererProps) {
  const highlighted = rest.active || rest.selected
  const playing = Boolean(
    (node.data as { playing?: boolean } | undefined)?.playing,
  )
  const showRing = rest.selected || playing
  const titleY = -(rest.size + TITLE_FONT_SIZE + 2)
  const ringColor = (node.fill as string | undefined) || FALLBACK_COLOR

  return (
    <>
      {node.icon ? (
        <Icon {...rest} node={node} image={node.icon} size={rest.size * 2} />
      ) : (
        <Sphere {...rest} node={node} />
      )}
      {showRing ? (
        <PaletteRing
          color={ringColor}
          size={rest.size}
          opacity={(rest.opacity ?? 1) * 0.22}
        />
      ) : null}
      <group position={[0, titleY, 2]}>
        <NodeLabel
          text={node.label ?? ""}
          ellipsis={26}
          fontUrl={GRAPH_FONT_URL}
          fontSize={TITLE_FONT_SIZE}
          opacity={rest.opacity}
          stroke={graphTheme.node.label.stroke}
          backgroundColor="#fafafa"
          backgroundOpacity={highlighted ? 0.92 : 0.72}
          padding={1.4}
          radius={0.35}
          active={highlighted}
          color={
            highlighted
              ? graphTheme.node.label.activeColor
              : graphTheme.node.label.color
          }
        />
      </group>
      {node.subLabel && highlighted ? (
        <group position={[0, titleY - TITLE_FONT_SIZE - 2, 2]}>
          <NodeLabel
            text={node.subLabel}
            ellipsis={30}
            fontUrl={GRAPH_FONT_URL}
            fontSize={ARTIST_FONT_SIZE}
            opacity={rest.opacity}
            stroke={graphTheme.node.subLabel?.stroke}
            backgroundColor="#fafafa"
            backgroundOpacity={0.85}
            padding={1.1}
            radius={0.3}
            active={highlighted}
            color={
              highlighted
                ? graphTheme.node.subLabel?.activeColor
                : graphTheme.node.subLabel?.color
            }
          />
        </group>
      ) : null}
    </>
  )
}

// Reagraph draws icons as square sprites, so covers are clipped to a
// circle on an offscreen canvas and cached as data URLs.
const circularCoverCache = new Map<string, string>()

function useCircularCovers(tracks: TrackOut[]): Map<string, string> {
  const [covers, setCovers] = useState<Map<string, string>>(
    () => new Map(circularCoverCache),
  )

  useEffect(() => {
    let cancelled = false
    for (const track of tracks) {
      if (!track.has_cover || circularCoverCache.has(track.id)) continue
      const image = new Image()
      image.onload = () => {
        const size = 128
        const canvas = document.createElement("canvas")
        canvas.width = size
        canvas.height = size
        const ctx = canvas.getContext("2d")
        if (!ctx) return
        ctx.beginPath()
        ctx.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2)
        ctx.clip()
        const crop = Math.min(image.width, image.height)
        ctx.drawImage(
          image,
          (image.width - crop) / 2,
          (image.height - crop) / 2,
          crop,
          crop,
          0,
          0,
          size,
          size,
        )
        circularCoverCache.set(track.id, canvas.toDataURL("image/png"))
        if (!cancelled) setCovers(new Map(circularCoverCache))
      }
      image.src = coverUrl(track.id)
    }
    return () => {
      cancelled = true
    }
  }, [tracks])

  return covers
}

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}

function trackLabel(track: TrackOut): string {
  return track.title
}

function TrackSeedArt({ track }: { track: TrackOut }) {
  return (
    <span
      className="size-9 shrink-0 overflow-hidden rounded-md bg-muted"
      style={{ backgroundColor: track.cover_color || undefined }}
    >
      {track.has_cover ? (
        <img
          src={trackCoverUrl(track.id)}
          alt=""
          className="size-full object-cover"
        />
      ) : null}
    </span>
  )
}

export default function GraphPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const focusParam = searchParams.get("focus")
  const limit = DEFAULT_LIMIT
  const player = useAudioPlayer()

  const [nodes, setNodes] = useState<Map<string, TrackOut>>(new Map())
  const [links, setLinks] = useState<Map<string, GraphLink>>(new Map())
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())
  const [focusId, setFocusId] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [expandingId, setExpandingId] = useState<string | null>(null)
  const [seedOptions, setSeedOptions] = useState<TrackOut[]>([])
  const [seedLoading, setSeedLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [booted, setBooted] = useState(false)
  const [layoutVersion, setLayoutVersion] = useState(0)

  const graphRef = useRef<GraphCanvasRef | null>(null)
  const bootRef = useRef(false)
  const focusParamRef = useRef(focusParam)
  // Set when we navigate locally so the URL effect doesn't fight mid-update.
  const pendingFocusRef = useRef<string | null>(null)
  const positionsRef = useRef<Map<string, Point>>(new Map())
  const framedOnceRef = useRef(false)
  const seedRequestRef = useRef(0)
  const seedDebounceRef = useRef<number | null>(null)
  // Bumped on every focus change / expand so slow responses can't rewind UI.
  const expandGenerationRef = useRef(0)
  const frameGenerationRef = useRef(0)

  const layoutOverrides: LayoutOverrides = useMemo(
    () =>
      ({
        getNodePosition: (id: string, _args: NodePositionArgs) => {
          const point = positionsRef.current.get(id)
          return { x: point?.x ?? 0, y: point?.y ?? 0, z: 0 }
        },
      }) as unknown as LayoutOverrides,
    [],
  )

  const seedTrack = useMemo(() => {
    if (!focusId) return null
    return (
      nodes.get(focusId) ??
      seedOptions.find((track) => track.id === focusId) ??
      null
    )
  }, [focusId, nodes, seedOptions])

  const seedItems = useMemo(() => {
    if (!seedTrack) return seedOptions
    if (seedOptions.some((track) => track.id === seedTrack.id)) return seedOptions
    return [seedTrack, ...seedOptions]
  }, [seedTrack, seedOptions])

  const fetchSeedOptions = useCallback(async (q: string) => {
    const requestId = ++seedRequestRef.current
    setSeedLoading(true)
    const { data, error: apiError } = await api.v1.listTracks({
      query: {
        q: q.trim() || null,
        status: "ready",
        limit: SEED_LIMIT,
      },
    })
    if (requestId !== seedRequestRef.current) return
    setSeedLoading(false)
    if (!apiError && data) setSeedOptions(data)
  }, [])

  const scheduleSeedSearch = useCallback(
    (q: string) => {
      if (seedDebounceRef.current !== null) {
        window.clearTimeout(seedDebounceRef.current)
      }
      seedDebounceRef.current = window.setTimeout(() => {
        void fetchSeedOptions(q)
      }, SEED_DEBOUNCE_MS)
    },
    [fetchSeedOptions],
  )

  const mergeGraph = useCallback(
    (graph: GraphResponseOut, seedId: string, replace: boolean) => {
      if (replace) positionsRef.current = new Map()
      placeNeighborhood(positionsRef.current, seedId, graph)
      setLayoutVersion((version) => version + 1)
      setNodes((prev) => {
        const next = replace ? new Map<string, TrackOut>() : new Map(prev)
        for (const node of graph.nodes) {
          next.set(node.track.id, node.track)
        }
        return next
      })
      setLinks((prev) => {
        const next = replace ? new Map<string, GraphLink>() : new Map(prev)
        for (const link of graph.links) {
          const key = edgeKey(link.source, link.target)
          next.set(key, { ...link, id: key })
        }
        return next
      })
      setExpandedIds((prev) => {
        const next = replace ? new Set<string>() : new Set(prev)
        next.add(seedId)
        return next
      })
      setFocusId(seedId)
      setSelectedId(seedId)
    },
    [],
  )

  // Frame the focus node and everything physically near it. Framing by
  // distance (not link topology) keeps the zoom consistent: linked nodes
  // placed far away in earlier expansions would otherwise widen the fit.
  const frameNeighborhood = useCallback((trackId: string) => {
    const center = positionsRef.current.get(trackId)
    if (!center) return
    const generation = ++frameGenerationRef.current
    const ids: string[] = []
    for (const [id, point] of positionsRef.current) {
      if (Math.hypot(point.x - center.x, point.y - center.y) <= FRAME_RADIUS) {
        ids.push(id)
      }
    }
    // On first mount a second pass wins over GraphCanvas's own
    // fit-all-nodes; afterwards a single quick fit is enough.
    const delays = framedOnceRef.current ? [150] : [150, 1200]
    framedOnceRef.current = true
    for (const delay of delays) {
      window.setTimeout(async () => {
        if (generation !== frameGenerationRef.current) return
        const graph = graphRef.current
        if (!graph) return
        // Fit sets the zoom for the neighborhood but centers on its
        // bounding box; re-target the focus so it lands mid-screen.
        await (graph.fitNodesInView(ids) as unknown as Promise<void>)
        if (generation !== frameGenerationRef.current) return
        graphRef.current?.centerGraph([trackId])
      }, delay)
    }
  }, [])

  const expandNode = useCallback(
    async (trackId: string, options: { replace?: boolean } = {}) => {
      const replace = options.replace === true
      if (!replace && expandedIds.has(trackId)) {
        // Drop any in-flight expand so it can't overwrite this focus later.
        expandGenerationRef.current += 1
        setExpandingId(null)
        setFocusId(trackId)
        setSelectedId(trackId)
        frameNeighborhood(trackId)
        return
      }

      const generation = ++expandGenerationRef.current
      setExpandingId(trackId)
      setError(null)
      const { data, error: apiError } = await api.v1.getGraph({
        query: { focus_track_id: trackId, limit },
      })
      if (generation !== expandGenerationRef.current) return
      setExpandingId(null)

      if (apiError || !data) {
        setError("Could not load neighborhood")
        return
      }
      if (data.nodes.length === 0) {
        setError("No indexed neighbors for this track")
        return
      }
      mergeGraph(data, trackId, replace)
      frameNeighborhood(trackId)
    },
    [expandedIds, limit, mergeGraph, frameNeighborhood],
  )

  const loadUnfocused = useCallback(async () => {
    setExpandingId("sample")
    setError(null)
    const { data, error: apiError } = await api.v1.getGraph({
      query: { limit },
    })
    setExpandingId(null)
    if (apiError || !data || data.nodes.length === 0) {
      setError("Could not load graph")
      return
    }
    const seed = data.nodes[0]?.track.id
    if (!seed) {
      setError("Could not load graph")
      return
    }
    mergeGraph(data, seed, true)
  }, [limit, mergeGraph])

  // camera-controls tuning reagraph exposes no props for: faster wheel
  // dolly, zooming toward the cursor. Polls until the canvas is live.
  useEffect(() => {
    const timer = window.setInterval(() => {
      const controls = graphRef.current?.getControls()
      if (!controls) return
      controls.dollySpeed = 3
      controls.dollyToCursor = true
      window.clearInterval(timer)
    }, 200)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (bootRef.current) return
    bootRef.current = true

    async function boot() {
      if (focusParam) {
        await expandNode(focusParam, { replace: true })
      } else {
        const { data } = await api.v1.listTracks({
          query: { status: "ready", limit: 1 },
        })
        const firstReady = data?.[0]
        if (firstReady) {
          pendingFocusRef.current = firstReady.id
          focusParamRef.current = firstReady.id
          setSearchParams(
            (prev) => {
              const next = new URLSearchParams(prev)
              next.set("focus", firstReady.id)
              if (!next.get("limit")) next.set("limit", String(DEFAULT_LIMIT))
              return next
            },
            { replace: true },
          )
          await expandNode(firstReady.id, { replace: true })
        } else {
          await loadUnfocused()
        }
      }
      setBooted(true)
      void fetchSeedOptions("")
    }

    void boot()
  }, [expandNode, fetchSeedOptions, focusParam, loadUnfocused, setSearchParams])

  useEffect(() => {
    return () => {
      if (seedDebounceRef.current !== null) {
        window.clearTimeout(seedDebounceRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (!booted || !focusParam) return
    // Local click/seed already owns this navigation — wait until the URL
    // catches up, otherwise a stale focusParam briefly re-expands the old seed
    // and cancels the in-flight neighbor load.
    if (pendingFocusRef.current != null) {
      if (pendingFocusRef.current === focusParam) {
        pendingFocusRef.current = null
        focusParamRef.current = focusParam
      }
      return
    }
    if (focusParamRef.current === focusParam) return
    focusParamRef.current = focusParam
    void expandNode(focusParam, { replace: true })
  }, [focusParam, booted, expandNode])

  const selectNode = useCallback(
    async (trackId: string) => {
      setSelectedId(trackId)
      setFocusId(trackId)
      pendingFocusRef.current = trackId
      focusParamRef.current = trackId
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        next.set("focus", trackId)
        next.set("limit", String(limit))
        return next
      })
      const track = nodes.get(trackId)
      if (track) void playTrack(track)
      if (!expandedIds.has(trackId)) {
        await expandNode(trackId)
        return
      }
      // Already expanded — still invalidate slower expands/frames.
      expandGenerationRef.current += 1
      setExpandingId(null)
      frameNeighborhood(trackId)
    },
    [
      expandedIds,
      expandNode,
      frameNeighborhood,
      limit,
      nodes,
      setSearchParams,
    ],
  )

  async function applySeed(trackId: string) {
    setFocusId(trackId)
    setSelectedId(trackId)
    pendingFocusRef.current = trackId
    focusParamRef.current = trackId
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set("focus", trackId)
      next.set("limit", String(limit))
      return next
    })
    await expandNode(trackId, { replace: true })
  }

  const nodeTracks = useMemo(() => [...nodes.values()], [nodes])
  const circularCovers = useCircularCovers(nodeTracks)

  const canvasNodes: GraphNode[] = useMemo(
    () =>
      nodeTracks.map((track) => ({
        id: track.id,
        label: track.title,
        subLabel: track.artist || undefined,
        size: nodeSize(track.id, expandedIds),
        fill: track.cover_color || FALLBACK_COLOR,
        icon: circularCovers.get(track.id),
        data: { playing: player.track?.id === track.id },
      })),
    [nodeTracks, expandedIds, circularCovers, player.track?.id],
  )

  const canvasEdges: GraphEdge[] = useMemo(
    () =>
      [...links.values()].map((link) => ({
        id: link.id,
        source: link.source,
        target: link.target,
        size: edgeSize(link.weight),
        arrowPlacement: "none" as const,
      })),
    [links],
  )

  const sizeById = useMemo(() => {
    const map = new Map<string, number>()
    for (const track of nodeTracks) {
      map.set(track.id, nodeSize(track.id, expandedIds))
    }
    return map
  }, [nodeTracks, expandedIds])

  const gradientEdges: GradientEdgeInput[] = useMemo(() => {
    const focusId = hoveredId ?? selectedId
    if (!focusId) return []
    // Only draw the star around the focused node — a full mesh is unreadable.
    return [...links.values()]
      .filter((link) => link.source === focusId || link.target === focusId)
      .map((link) => {
        const source = nodes.get(link.source)
        const target = nodes.get(link.target)
        return {
          id: link.id,
          source: link.source,
          target: link.target,
          size: edgeSize(link.weight),
          sourceColor: source?.cover_color || FALLBACK_COLOR,
          targetColor: target?.cover_color || FALLBACK_COLOR,
        }
      })
  }, [links, nodes, hoveredId, selectedId])

  const selected = selectedId ? nodes.get(selectedId) : null

  const linkedNeighbors = useMemo(() => {
    if (!selectedId) return []
    const rows: { track: TrackOut; link: GraphLink }[] = []
    for (const link of links.values()) {
      const otherId =
        link.source === selectedId
          ? link.target
          : link.target === selectedId
            ? link.source
            : null
      if (!otherId) continue
      const track = nodes.get(otherId)
      if (!track) continue
      rows.push({ track, link })
    }
    return rows.sort((a, b) => b.link.weight - a.link.weight).slice(0, 6)
  }, [selectedId, links, nodes])

  const actives = useMemo(() => {
    const activeId = hoveredId ?? selectedId
    if (!activeId) return []
    const ids = new Set<string>([activeId])
    for (const link of links.values()) {
      if (link.source === activeId || link.target === activeId) {
        ids.add(link.source)
        ids.add(link.target)
        ids.add(link.id)
      }
    }
    return [...ids]
  }, [hoveredId, selectedId, links])

  const selections = useMemo(
    () => (selectedId ? [selectedId] : []),
    [selectedId],
  )

  const handleNodeClick = useCallback(
    (node: { id: string }) => {
      void selectNode(node.id)
    },
    [selectNode],
  )
  const handleNodeOver = useCallback(
    (node: { id: string }) => setHoveredId(node.id),
    [],
  )
  const handleNodeOut = useCallback(() => setHoveredId(null), [])

  return (
    <div className="relative h-full min-h-0 w-full overflow-hidden overscroll-none">
      <div className="absolute inset-0">
        {canvasNodes.length > 0 ? (
          <GraphCanvas
            ref={graphRef}
            nodes={canvasNodes}
            edges={canvasEdges}
            theme={graphTheme}
            cameraMode="pan"
            labelType="none"
            layoutType="custom"
            minDistance={250}
            minNodeSize={MIN_NODE_SIZE}
            maxNodeSize={MAX_NODE_SIZE}
            layoutOverrides={layoutOverrides}
            edgeInterpolation="curved"
            edgeArrowPosition="none"
            selections={selections}
            actives={actives}
            renderNode={renderTrackNode}
            onNodeClick={handleNodeClick}
            onNodePointerOver={handleNodeOver}
            onNodePointerOut={handleNodeOut}
          >
            <GraphGradientEdges
              edges={gradientEdges}
              positionsRef={positionsRef}
              sizeById={sizeById}
              actives={actives}
              layoutVersion={layoutVersion}
            />
          </GraphCanvas>
        ) : (
          <div className="flex h-full items-center justify-center">
            <p className="text-muted-foreground text-sm">
              {expandingId ? "Loading neighborhood…" : "No graph yet"}
            </p>
          </div>
        )}
      </div>

      <div className="pointer-events-none absolute inset-0 z-10">
        <div className="pointer-events-auto absolute top-4 left-4 flex w-[min(24rem,calc(100%-2rem))] flex-col gap-3 rounded-xl border bg-background/95 p-4 shadow-sm backdrop-blur">
          <div>
            <h1 className="flex items-center gap-2 text-base font-medium tracking-tight">
              <Graph className="size-4 shrink-0" weight="regular" aria-hidden />
              Graph
              <span
                className="inline-flex items-center gap-1 rounded-full bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground tabular-nums"
                title={`${nodes.size} tracks in view`}
              >
                <MusicNote className="size-3" weight="regular" aria-hidden />
                {nodes.size}
              </span>
            </h1>
            <p className="text-muted-foreground text-xs leading-relaxed">
              Explore tracks that sound alike.
              {expandingId ? " Expanding…" : null}
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label htmlFor="seed">Seed track</Label>
            <Combobox
              items={seedItems}
              value={seedTrack}
              onValueChange={(track) => {
                if (track) void applySeed(track.id)
              }}
              onInputValueChange={(value) => {
                scheduleSeedSearch(value)
              }}
              onOpenChange={(open) => {
                if (open && seedOptions.length === 0) void fetchSeedOptions("")
              }}
              itemToStringLabel={trackLabel}
              isItemEqualToValue={(item, value) => item.id === value.id}
              filter={null}
              disabled={expandingId !== null}
            >
              <ComboboxInput
                id="seed"
                placeholder="Search title or artist…"
                className="w-full"
                startAddon={seedTrack ? <TrackSeedArt track={seedTrack} /> : null}
                subtitle={
                  seedTrack
                    ? seedTrack.artist || "Unknown artist"
                    : null
                }
              />
              <ComboboxContent className="z-[60]">
                <ComboboxEmpty>
                  {seedLoading ? "Searching…" : "No tracks found."}
                </ComboboxEmpty>
                <ComboboxList>
                  {(track: TrackOut) => (
                    <ComboboxItem key={track.id} value={track}>
                      <span className="flex min-w-0 items-center gap-2">
                        <TrackSeedArt track={track} />
                        <span className="min-w-0 truncate">
                          <span className="block truncate font-medium">
                            {track.title}
                          </span>
                          <span className="text-muted-foreground block truncate text-xs">
                            {track.artist || "Unknown artist"}
                          </span>
                        </span>
                      </span>
                    </ComboboxItem>
                  )}
                </ComboboxList>
              </ComboboxContent>
            </Combobox>
          </div>

          {error ? <p className="text-destructive text-sm">{error}</p> : null}
        </div>

        {selected ? (
          <aside className="pointer-events-auto absolute top-4 right-4 flex w-[min(22rem,calc(100%-2rem))] flex-col gap-3 rounded-xl border bg-background/95 p-4 shadow-sm backdrop-blur">
            <div className="flex gap-3">
              <div
                className="size-14 shrink-0 overflow-hidden rounded-lg bg-muted"
                style={{ backgroundColor: selected.cover_color || FALLBACK_COLOR }}
              >
                {selected.has_cover ? (
                  <img
                    src={coverUrl(selected.id)}
                    alt=""
                    className="size-full object-cover"
                  />
                ) : null}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{selected.title}</p>
                <p className="text-muted-foreground truncate text-sm">
                  {selected.artist || "Unknown artist"}
                </p>
              </div>
              <Button
                type="button"
                size="icon"
                variant="outline"
                className="size-9 shrink-0"
                aria-label={
                  player.track?.id === selected.id && player.playing
                    ? "Pause"
                    : "Play"
                }
                onClick={() => {
                  void toggleTrack(selected)
                }}
              >
                {player.track?.id === selected.id && player.playing ? (
                  <Pause weight="fill" />
                ) : (
                  <Play weight="fill" />
                )}
              </Button>
            </div>

            {linkedNeighbors.length > 0 ? (
              <div className="flex flex-col gap-2">
                <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
                  Linked
                </p>
                <ul className="flex flex-col gap-1">
                  {linkedNeighbors.map(({ track, link: _link }) => (
                    <li key={track.id}>
                      <button
                        type="button"
                        className="hover:bg-muted flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm"
                        onClick={() => void selectNode(track.id)}
                      >
                        <span
                          className="size-9 shrink-0 overflow-hidden rounded-md bg-muted"
                          style={{
                            backgroundColor: track.cover_color || FALLBACK_COLOR,
                          }}
                        >
                          {track.has_cover ? (
                            <img
                              src={coverUrl(track.id)}
                              alt=""
                              className="size-full object-cover"
                            />
                          ) : null}
                        </span>
                        <span className="min-w-0 flex-1 truncate">
                          <span className="block truncate font-medium">
                            {track.title}
                          </span>
                          <span className="text-muted-foreground block truncate text-xs">
                            {track.artist || "Unknown artist"}
                            {/*
                            {percent(_link.weight)} · audio{" "}
                            {percent(_link.audio_weight)} · profile{" "}
                            {percent(_link.profile_weight)}
                            */}
                          </span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">No linked neighbors yet.</p>
            )}
          </aside>
        ) : null}

        <div
          className="graph-camera-controls pointer-events-auto absolute right-4 z-20 flex flex-col overflow-hidden rounded-xl border bg-background/95 shadow-sm backdrop-blur"
          role="toolbar"
          aria-label="Graph camera"
        >
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-9 rounded-none"
            aria-label="Zoom in"
            onClick={() => graphRef.current?.zoomIn()}
          >
            <MagnifyingGlassPlus weight="regular" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-9 rounded-none border-t border-border"
            aria-label="Zoom out"
            onClick={() => graphRef.current?.zoomOut()}
          >
            <MagnifyingGlassMinus weight="regular" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-9 rounded-none border-t border-border"
            aria-label="Focus seed"
            disabled={!focusId}
            onClick={() => {
              if (focusId) frameNeighborhood(focusId)
            }}
          >
            <Crosshair weight="regular" />
          </Button>
        </div>
      </div>
    </div>
  )
}
