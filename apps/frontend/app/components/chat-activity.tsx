import type { ComponentType } from "react"
import {
  Brain,
  ChartBar,
  CirclesThreePlus,
  Graph,
  MagnifyingGlass,
  MusicNotes,
  Playlist,
  Plus,
  SpinnerGap,
  Trash,
  Wrench,
} from "@phosphor-icons/react"

import { cn } from "~/lib/utils"

export type ChatActivityStep = {
  id: string
  kind: "thinking" | "tool"
  name?: string
  label: string
  done?: boolean
}

const TOOL_META: Record<
  string,
  { label: string; Icon: ComponentType<{ className?: string; weight?: "regular" | "bold" }> }
> = {
  search_vibe: { label: "AI vibe search", Icon: Brain },
  search_metadata: { label: "Searching by title/artist", Icon: MagnifyingGlass },
  similar_tracks: { label: "AI similar tracks", Icon: CirclesThreePlus },
  graph_neighborhood: { label: "Exploring the graph", Icon: Graph },
  get_track: { label: "Looking up a track", Icon: MusicNotes },
  list_tracks: { label: "Browsing the catalog", Icon: MusicNotes },
  library_stats: { label: "Checking library stats", Icon: ChartBar },
  list_playlists: { label: "Listing playlists", Icon: Playlist },
  get_playlist: { label: "Opening a playlist", Icon: Playlist },
  create_playlist: { label: "Creating a playlist", Icon: Plus },
  update_playlist: { label: "Updating a playlist", Icon: Playlist },
  add_tracks_to_playlist: { label: "Adding tracks to playlist", Icon: Plus },
  remove_tracks_from_playlist: { label: "Removing tracks from playlist", Icon: Trash },
  reorder_playlist: { label: "Reordering playlist", Icon: Playlist },
  delete_playlist: { label: "Deleting a playlist", Icon: Trash },
  // Legacy name from older chats/traces
  search_text: { label: "AI vibe search", Icon: Brain },
}

export function toolActivityLabel(name: string): string {
  return TOOL_META[name]?.label ?? `Using ${name.replaceAll("_", " ")}`
}

export function activityFromStatus(
  phase: "thinking" | "tool" | "cancelled",
  name?: string | null,
): ChatActivityStep | null {
  if (phase === "cancelled") return null
  if (phase === "thinking") {
    return { id: "thinking", kind: "thinking", label: "Thinking" }
  }
  const toolName = name?.trim() || "tool"
  return {
    id: `tool-${toolName}-${Date.now()}`,
    kind: "tool",
    name: toolName,
    label: toolActivityLabel(toolName),
  }
}

function StepIcon({
  step,
  active,
}: {
  step: ChatActivityStep
  active: boolean
}) {
  if (active) {
    return <SpinnerGap className="size-3.5 shrink-0 animate-spin" weight="bold" />
  }
  if (step.kind === "thinking") {
    return <Brain className="size-3.5 shrink-0" weight="bold" />
  }
  const Icon = (step.name && TOOL_META[step.name]?.Icon) || Wrench
  return <Icon className="size-3.5 shrink-0" weight="bold" />
}

export function ChatActivity({
  steps,
  className,
}: {
  steps: ChatActivityStep[]
  className?: string
}) {
  if (steps.length === 0) return null

  return (
    <ul className={cn("flex flex-col gap-1.5", className)}>
      {steps.map((step, index) => {
        const active = !step.done && index === steps.length - 1
        return (
          <li
            key={step.id}
            className={cn(
              "text-muted-foreground flex items-center gap-2 text-sm transition-all duration-300 ease-out",
              "animate-in fade-in slide-in-from-bottom-1 fill-mode-both",
              active ? "opacity-100" : "opacity-70",
            )}
            style={{ animationDelay: `${Math.min(index, 4) * 40}ms` }}
          >
            <StepIcon step={step} active={active} />
            <span className={cn(active && "animate-pulse")}>{step.label}…</span>
          </li>
        )
      })}
    </ul>
  )
}
