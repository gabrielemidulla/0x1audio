import type { PlaylistSummaryOut } from "~/lib/api"

let snapshot: PlaylistSummaryOut[] | null = null
let entered = false

export function readPlaylistsSnapshot(): PlaylistSummaryOut[] | null {
  return snapshot
}

export function writePlaylistsSnapshot(next: PlaylistSummaryOut[]): void {
  snapshot = next
}

export function hasPlaylistsEntered(): boolean {
  return entered
}

export function markPlaylistsEntered(): void {
  entered = true
}
