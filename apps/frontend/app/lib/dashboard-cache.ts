import type { TrackOut } from "~/lib/api"

type DashboardSnapshot = {
  recent: TrackOut[]
  pendingJobs: number
}

let snapshot: DashboardSnapshot | null = null
let entered = false

export function readDashboardSnapshot(): DashboardSnapshot | null {
  return snapshot
}

export function writeDashboardSnapshot(next: DashboardSnapshot): void {
  snapshot = next
}

export function hasDashboardEntered(): boolean {
  return entered
}

export function markDashboardEntered(): void {
  entered = true
}
