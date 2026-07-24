import {
  CornersOut,
  Graph,
  Pause,
  PictureInPicture,
  Play,
  SpeakerHigh,
  X,
} from "@phosphor-icons/react"
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react"
import { Link } from "react-router"

import {
  closePlayer,
  formatTime,
  playTrack,
  readSpectrumBands,
  seekTrack,
  setVolume,
  toggleTrack,
  useAudioPlayer,
} from "~/lib/audio-player"
import {
  extractCoverPalette,
  paletteFromHex,
  softenPlayerPalette,
  type CoverPalette,
} from "~/lib/cover-palette"
import { api, trackCoverUrl, type TrackOut } from "~/lib/api"
import { ArtistCredits, artistCreditsText } from "~/components/artist-credits"
import { MarqueeText } from "~/components/marquee-text"
import { Button } from "~/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "~/components/ui/tooltip"
import { TrackWaveform } from "~/components/track-waveform"
import { cn } from "~/lib/utils"

const PLAYER_MS = 320
const PLAYER_EASE = "cubic-bezier(0.22, 1, 0.36, 1)"

const ENTER_KEYFRAMES: Keyframe[] = [
  { transform: "translate3d(0, 115%, 0)", filter: "blur(8px)" },
  { transform: "translate3d(0, 0, 0)", filter: "blur(0px)" },
]

const EXIT_KEYFRAMES: Keyframe[] = [
  { transform: "translate3d(0, 0, 0)", filter: "blur(0px)" },
  { transform: "translate3d(0, 115%, 0)", filter: "blur(8px)" },
]

function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches
}

function clearMotionStyles(el: HTMLElement) {
  el.style.removeProperty("transform")
  el.style.removeProperty("filter")
}

function runEnter(el: HTMLElement) {
  if (prefersReducedMotion()) {
    el.style.transform = "translate3d(0, 0, 0)"
    el.style.filter = "blur(0px)"
    return
  }
  clearMotionStyles(el)
  el.getAnimations().forEach((anim) => anim.cancel())
  el.animate(ENTER_KEYFRAMES, {
    duration: PLAYER_MS,
    easing: PLAYER_EASE,
    fill: "forwards",
  })
}

export function FloatingTrackPlayer() {
  const player = useAudioPlayer()
  const glossRef = useRef<HTMLDivElement>(null)
  const shellRef = useRef<HTMLDivElement | null>(null)
  const activeTrackRef = useRef(player.track)
  const sessionRef = useRef(false)
  const [mini, setMini] = useState(false)
  const [samples, setSamples] = useState<number[] | null>(null)
  const [waveformDuration, setWaveformDuration] = useState<number | null>(null)
  const [palette, setPalette] = useState<CoverPalette>(() =>
    softenPlayerPalette(paletteFromHex(null)),
  )
  const [renderTrack, setRenderTrack] = useState<TrackOut | null>(player.track)

  activeTrackRef.current = player.track

  const track = renderTrack
  const activeId = player.track?.id ?? null
  const duration =
    player.duration || waveformDuration || track?.duration_s || 0
  const progress = duration > 0 ? player.currentTime / duration : 0

  // Start the enter slide when the card DOM node attaches (not via CSS
  // transition — those skip when the node mounts already "open").
  const bindShell = useCallback((node: HTMLDivElement | null) => {
    shellRef.current = node
    if (!node) return
    if (!activeTrackRef.current) return
    if (sessionRef.current) {
      // Same open session (Strict Mode re-attach): still need motion on the
      // new node, but only if it isn't already animating/finished.
      const busy = node
        .getAnimations()
        .some(
          (anim) =>
            anim.playState === "running" || anim.playState === "finished",
        )
      if (busy) return
    }
    sessionRef.current = true
    runEnter(node)
  }, [])

  useEffect(() => {
    if (player.track) {
      setRenderTrack(player.track)
      // Track swap keeps the same DOM node → bindShell is not re-called →
      // no re-slide. Fresh open mounts a new node → bindShell runs enter.
      return
    }

    const el = shellRef.current
    if (!el || !sessionRef.current) {
      sessionRef.current = false
      setRenderTrack(null)
      return
    }

    sessionRef.current = false
    if (prefersReducedMotion()) {
      clearMotionStyles(el)
      setRenderTrack(null)
      return
    }

    el.getAnimations().forEach((anim) => anim.cancel())
    const anim = el.animate(EXIT_KEYFRAMES, {
      duration: PLAYER_MS,
      easing: PLAYER_EASE,
      fill: "forwards",
    })
    let finished = false
    const finish = () => {
      if (finished) return
      finished = true
      clearMotionStyles(el)
      setRenderTrack(null)
    }
    void anim.finished.then(finish).catch(finish)
    const timer = window.setTimeout(finish, PLAYER_MS + 50)
    return () => window.clearTimeout(timer)
  }, [activeId, player.track])

  useEffect(() => {
    const gloss = glossRef.current
    if (!gloss || !track) return
    if (prefersReducedMotion()) {
      gloss.style.setProperty("--player-bass", "0")
      gloss.style.setProperty("--player-mid", "0")
      gloss.style.setProperty("--player-treble", "0")
      gloss.style.setProperty("--player-energy", "0")
      return
    }

    let frame = 0
    let bass = 0
    let mid = 0
    let treble = 0
    let energy = 0

    const tick = () => {
      const spectrum = player.playing
        ? readSpectrumBands()
        : { bass: 0, mid: 0, treble: 0, energy: 0 }
      const blend = (
        prev: number,
        next: number,
        attack: number,
        release: number,
      ) => prev + (next - prev) * (next > prev ? attack : release)

      bass = blend(
        bass,
        spectrum.bass,
        player.playing ? 0.55 : 0.12,
        player.playing ? 0.09 : 0.06,
      )
      mid = blend(
        mid,
        spectrum.mid,
        player.playing ? 0.22 : 0.1,
        player.playing ? 0.1 : 0.07,
      )
      treble = blend(
        treble,
        spectrum.treble,
        player.playing ? 0.18 : 0.1,
        player.playing ? 0.11 : 0.07,
      )
      energy = blend(
        energy,
        spectrum.energy,
        player.playing ? 0.4 : 0.1,
        player.playing ? 0.08 : 0.06,
      )

      gloss.style.setProperty("--player-bass", bass.toFixed(3))
      gloss.style.setProperty("--player-mid", mid.toFixed(3))
      gloss.style.setProperty("--player-treble", treble.toFixed(3))
      gloss.style.setProperty("--player-energy", energy.toFixed(3))
      gloss.dataset.dancing = player.playing && energy > 0.03 ? "true" : "false"
      frame = window.requestAnimationFrame(tick)
    }

    frame = window.requestAnimationFrame(tick)
    return () => window.cancelAnimationFrame(frame)
  }, [track?.id, player.playing])

  useEffect(() => {
    if (!track) {
      setSamples(null)
      setWaveformDuration(null)
      return
    }
    let cancelled = false
    setSamples(null)
    setWaveformDuration(null)
    void api.v1
      .getTrackWaveform({ path: { track_id: track.id } })
      .then((result) => {
        if (cancelled || result.error || !result.data) return
        setSamples(result.data.samples)
        setWaveformDuration(result.data.duration_s)
      })
    return () => {
      cancelled = true
    }
  }, [track?.id])

  useEffect(() => {
    if (!track) return
    let cancelled = false
    const fallback = softenPlayerPalette(paletteFromHex(track.cover_color))
    setPalette(fallback)
    if (!track.has_cover) return
    void extractCoverPalette(trackCoverUrl(track.id))
      .then((next) => {
        if (!cancelled) setPalette(softenPlayerPalette(next))
      })
      .catch(() => {
        if (!cancelled) setPalette(fallback)
      })
    return () => {
      cancelled = true
    }
  }, [track?.id, track?.has_cover, track?.cover_color])

  const shellStyle = useMemo(() => {
    const colors = palette.colors
    const c1 = colors[0] ?? "#334155"
    const c2 = colors[1] ?? c1
    const c3 = colors[2] ?? c2
    const c4 = colors[3] ?? c1
    const c5 = colors[4] ?? c2
    const c6 = colors[5] ?? c3
    const fg = palette.onDark ? "#f8fafc" : "#0f172a"
    const muted = palette.onDark
      ? "rgba(248, 250, 252, 0.72)"
      : "rgba(15, 23, 42, 0.68)"
    const waveIdle = palette.onDark
      ? "rgba(248, 250, 252, 0.28)"
      : "rgba(15, 23, 42, 0.22)"
    return {
      "--player-c1": c1,
      "--player-c2": c2,
      "--player-c3": c3,
      "--player-c4": c4,
      "--player-c5": c5,
      "--player-c6": c6,
      "--player-fg": fg,
      "--player-fg-muted": muted,
      "--player-wave-active": fg,
      "--player-wave-idle": waveIdle,
      "--volume-progress": `${player.volume * 100}%`,
      color: fg,
    } as CSSProperties
  }, [palette, player.volume])

  const ghostIconClass = cn(
    "size-8 focus-visible:shadow-none",
    palette.onDark
      ? [
          "text-white/70 hover:bg-white/10 hover:text-white",
          "active:!bg-white/15 focus-visible:!bg-white/10",
        ].join(" ")
      : [
          "text-slate-950/70 hover:bg-black/10 hover:text-slate-950",
          "active:!bg-black/15 focus-visible:!bg-black/10",
        ].join(" "),
  )

  if (!track) return null

  const actionIcons = (
    <TooltipProvider delay={500}>
      <div className="flex shrink-0 items-center gap-0.5">
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className={ghostIconClass}
                aria-label="Go to the graph"
                render={<Link to={`/graph?focus=${track.id}`} />}
              />
            }
          >
            <Graph className="size-4" />
          </TooltipTrigger>
          <TooltipContent side="top">Go to the graph</TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className={cn("hidden md:inline-flex", ghostIconClass)}
                aria-label={mini ? "Hide mini player" : "Show mini player"}
                aria-pressed={mini}
                onClick={() => setMini((value) => !value)}
              />
            }
          >
            {mini ? (
              <CornersOut className="size-4" weight="regular" />
            ) : (
              <PictureInPicture className="size-4" weight="regular" />
            )}
          </TooltipTrigger>
          <TooltipContent side="top">
            {mini ? "Hide mini player" : "Show mini player"}
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className={ghostIconClass}
                aria-label="Close player"
                onClick={() => closePlayer()}
              />
            }
          >
            <X className="size-4" />
          </TooltipTrigger>
          <TooltipContent side="top">Close player</TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  )

  return (
    <div
      ref={bindShell}
      data-open="true"
      data-mini={mini ? "true" : undefined}
      data-on-dark={palette.onDark ? "true" : "false"}
      className={cn(
        "app-floating-player fixed bottom-3 left-4 right-4 z-50 w-auto overflow-hidden rounded-xl border-0 bg-transparent py-0 shadow-2xl ring-0",
      )}
      style={shellStyle}
    >
      <div ref={glossRef} className="player-gloss" aria-hidden>
        <span className="player-gloss-mesh" />
        <span className="player-gloss-wave player-gloss-wave-a" />
        <span className="player-gloss-wave player-gloss-wave-b" />
        <span className="player-gloss-blob player-gloss-blob-a" />
        <span className="player-gloss-blob player-gloss-blob-b" />
        <span className="player-gloss-blob player-gloss-blob-c" />
        <span className="player-gloss-blob player-gloss-blob-d" />
        <span className="player-gloss-blob player-gloss-blob-e" />
        <span className="player-gloss-sheen" />
      </div>

      <div
        className={cn(
          "relative z-10 px-2.5 py-1.5 sm:px-3 sm:py-2",
          mini
            ? "flex items-center gap-2"
            : "flex flex-col gap-2 sm:gap-3 lg:flex-row lg:items-center",
        )}
      >
        <div
          className={cn(
            "flex min-w-0 items-center gap-3",
            mini ? "min-w-0 flex-1" : "flex-1 lg:max-w-md lg:w-80 lg:flex-none",
          )}
        >
          <div
            className="size-11 shrink-0 overflow-hidden rounded-xl sm:size-12"
            style={{
              backgroundColor: track.cover_color || palette.colors[0],
            }}
          >
            {track.has_cover ? (
              <img
                src={trackCoverUrl(track.id)}
                alt=""
                className="size-full object-cover"
              />
            ) : null}
          </div>
          <div className="min-w-0 flex-1">
            <MarqueeText
              className="text-sm font-medium"
              contentKey={`${track.id}:title:${track.title}`}
            >
              {track.title}
            </MarqueeText>
            <MarqueeText
              className="text-xs"
              style={{ color: "var(--player-fg-muted)" }}
              contentKey={`${track.id}:artist:${artistCreditsText(track)}`}
            >
              <ArtistCredits
                track={track}
                className="overflow-visible text-xs whitespace-nowrap text-inherit"
              />
            </MarqueeText>
          </div>

          {/* Phone full player: keep icons on the title row, pinned right. */}
          {!mini ? (
            <div className="ml-auto flex shrink-0 lg:hidden">{actionIcons}</div>
          ) : null}
        </div>

        <div
          className={cn(
            "flex items-center gap-2.5",
            mini ? "shrink-0" : "min-w-0 flex-1",
          )}
        >
          <Button
            type="button"
            size="icon"
            className={cn(
              "size-9 shrink-0 rounded-full border-0 shadow-none after:hidden sm:size-10",
              "hover:shadow-none focus-visible:shadow-none active:shadow-none",
              mini && "ml-1",
              palette.onDark
                ? "bg-white/20 text-white hover:bg-white/30"
                : "bg-black/15 text-slate-950 hover:bg-black/25",
            )}
            aria-label={player.playing ? "Pause" : "Play"}
            onClick={() => {
              void toggleTrack(track)
            }}
          >
            {player.playing ? (
              <Pause weight="fill" />
            ) : (
              <Play weight="fill" />
            )}
          </Button>

          {!mini ? (
            <>
              <span
                className="w-9 text-right text-xs tabular-nums"
                style={{ color: "var(--player-fg-muted)" }}
              >
                {formatTime(player.currentTime)}
              </span>
              {samples && samples.length > 0 ? (
                <TrackWaveform
                  samples={samples}
                  progress={progress}
                  duration={duration}
                  currentTime={player.currentTime}
                  onSeek={(seconds) => {
                    if (!player.playing && player.track?.id === track.id) {
                      void playTrack(track).then(() => seekTrack(seconds))
                      return
                    }
                    seekTrack(seconds)
                  }}
                />
              ) : (
                <div
                  className="h-10 min-w-0 flex-1 rounded-md"
                  style={{
                    backgroundColor: palette.onDark
                      ? "rgba(255,255,255,0.12)"
                      : "rgba(0,0,0,0.08)",
                  }}
                />
              )}
              <span
                className="w-9 text-xs tabular-nums"
                style={{ color: "var(--player-fg-muted)" }}
              >
                {formatTime(duration)}
              </span>
            </>
          ) : null}
        </div>

        {/* Desktop full + mini: actions on the trailing edge. */}
        <div
          className={cn(
            "flex shrink-0 items-center justify-end gap-1.5",
            mini ? "ml-0.5" : "hidden lg:flex",
          )}
        >
          {!mini ? (
            <label
              className="hidden items-center gap-2 px-1 md:flex"
              style={{ color: "var(--player-fg-muted)" }}
            >
              <SpeakerHigh className="size-4" aria-hidden />
              <span className="sr-only">Volume</span>
              <input
                className="music-player-volume music-player-volume-adaptive w-24"
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={player.volume}
                onChange={(event) => setVolume(Number(event.target.value))}
                aria-label="Volume"
              />
            </label>
          ) : null}

          {actionIcons}
        </div>
      </div>
    </div>
  )
}
