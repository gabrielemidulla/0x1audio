import { useEffect, useRef, useState } from "react"
import { Queue } from "@phosphor-icons/react"

import { api, type JobOut } from "~/lib/api"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "~/components/ui/alert-dialog"
import { Badge } from "~/components/ui/badge"
import { Button } from "~/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "~/components/ui/card"
import {
  Progress,
  ProgressLabel,
  ProgressValue,
} from "~/components/ui/progress"

const ACTIVE = new Set(["queued", "importing", "indexing"])

/** Sliding window of ready counts for ETA (successful index rate only). */
type Pace = { samples: { at: number; ready: number }[] }

function jobPercent(job: JobOut): number {
  if (job.total_files <= 0) return job.phase === "complete" ? 100 : 0
  const terminal = job.ready_files + job.failed_files
  return Math.min(100, Math.round((terminal / job.total_files) * 100))
}

function phaseVariant(phase: JobOut["phase"]) {
  if (phase === "complete") return "default" as const
  if (phase === "failed") return "destructive" as const
  return "secondary" as const
}

function formatEta(seconds: number | null): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return "—"
  if (seconds < 60) return `~${Math.max(1, Math.ceil(seconds))}s`
  const minutes = Math.ceil(seconds / 60)
  if (minutes < 60) return `~${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours >= 24) return `~${Math.ceil(hours / 24)}d`
  const rem = minutes % 60
  return rem > 0 ? `~${hours}h ${rem}m` : `~${hours}h`
}

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  })
}

function pushPace(pace: Map<string, Pace>, job: JobOut, now: number) {
  if (job.phase !== "indexing") return
  let entry = pace.get(job.id)
  if (!entry) {
    entry = { samples: [] }
    pace.set(job.id, entry)
  }
  const last = entry.samples[entry.samples.length - 1]
  if (last && last.ready === job.ready_files && now - last.at < 2000) return
  entry.samples.push({ at: now, ready: job.ready_files })
  // Keep ~60s of history.
  const cutoff = now - 60_000
  entry.samples = entry.samples.filter((s) => s.at >= cutoff)
  if (entry.samples.length > 30) entry.samples = entry.samples.slice(-30)
}

function etaSeconds(job: JobOut, pace: Map<string, Pace>): number | null {
  if (job.phase !== "indexing" || job.pending_files <= 0) return null
  const entry = pace.get(job.id)
  if (!entry || entry.samples.length < 2) return null

  const first = entry.samples[0]
  const last = entry.samples[entry.samples.length - 1]
  const elapsed = (last.at - first.at) / 1000
  const gained = last.ready - first.ready
  // Need a meaningful window and at least a few successful indexes.
  if (elapsed < 10 || gained < 3) return null

  const rate = gained / elapsed // ready tracks / second
  if (rate <= 0) return null
  return job.pending_files / rate
}

function progressLabel(job: JobOut): string {
  if (job.phase === "queued") return "Waiting to start"
  if (job.phase === "importing") {
    return job.total_files > 0
      ? `Importing · ${job.ready_files} / ${job.total_files} indexed so far`
      : "Importing files…"
  }
  if (job.total_files <= 0) return "Preparing…"
  const parts = [`${job.ready_files} ready`]
  if (job.pending_files > 0) parts.push(`${job.pending_files} pending`)
  if (job.failed_files > 0) parts.push(`${job.failed_files} failed`)
  return `${job.ready_files + job.failed_files} / ${job.total_files} · ${parts.join(" · ")}`
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobOut[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState<string | null>(null)
  const [retrying, setRetrying] = useState<string | null>(null)
  const [confirmJob, setConfirmJob] = useState<JobOut | null>(null)
  const paceRef = useRef(new Map<string, Pace>())

  async function refresh() {
    const { data, error: apiError } = await api.v1.listJobs()
    if (apiError || !data) {
      setError("Could not load jobs")
      return
    }
    setError(null)

    const tick = Date.now()
    const pace = paceRef.current
    const active = new Set<string>()
    for (const job of data) {
      if (!ACTIVE.has(job.phase)) continue
      active.add(job.id)
      pushPace(pace, job, tick)
    }
    for (const id of [...pace.keys()]) {
      if (!active.has(id)) pace.delete(id)
    }

    setJobs(data)
  }

  async function cancelJob(jobId: string) {
    setCancelling(jobId)
    setError(null)
    const { error: apiError } = await api.v1.cancelJob({ path: { job_id: jobId } })
    setCancelling(null)
    setConfirmJob(null)
    if (apiError) {
      setError("Could not cancel job")
      return
    }
    await refresh()
  }

  async function retryFailed(jobId: string) {
    setRetrying(jobId)
    setError(null)
    const { error: apiError } = await api.v1.retryFailedJob({ path: { job_id: jobId } })
    setRetrying(null)
    if (apiError) {
      setError("Could not retry failed tracks")
      return
    }
    await refresh()
  }

  useEffect(() => {
    void refresh()
  }, [])

  useEffect(() => {
    const pending = jobs?.some((job) => ACTIVE.has(job.phase))
    if (!pending) return
    const id = window.setInterval(() => {
      void refresh()
    }, 2000)
    return () => window.clearInterval(id)
  }, [jobs])

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-2xl font-medium tracking-tight">Jobs</h1>
        <p className="text-muted-foreground text-sm leading-relaxed">
          Indexing progress for catalog imports. Active jobs refresh every 2 seconds.
        </p>
      </div>

      {error ? <p className="text-destructive text-sm">{error}</p> : null}

      {jobs === null ? (
        <p className="text-muted-foreground text-sm">Loading…</p>
      ) : jobs.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Queue className="size-4" />
              No jobs yet
            </CardTitle>
            <CardDescription>
              Upload a ZIP from the Catalog page to start indexing.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {jobs.map((job) => {
            const percent = jobPercent(job)
            const eta =
              job.phase === "queued" || job.phase === "importing"
                ? "Waiting…"
                : job.phase === "indexing"
                  ? formatEta(etaSeconds(job, paceRef.current))
                  : "—"
            const canCancel = ACTIVE.has(job.phase)
            const canRetry = job.failed_files > 0
            const busy = cancelling === job.id || retrying === job.id

            return (
              <Card key={job.id}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex flex-col gap-1">
                      <CardTitle className="truncate text-base">{job.name}</CardTitle>
                      <CardDescription>
                        Started {formatWhen(job.created_at)}
                      </CardDescription>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge variant={phaseVariant(job.phase)}>{job.phase}</Badge>
                      {canRetry ? (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={busy}
                          onClick={() => void retryFailed(job.id)}
                        >
                          {retrying === job.id ? "Retrying…" : "Retry failed"}
                        </Button>
                      ) : null}
                      {canCancel ? (
                        <Button
                          variant="destructive"
                          size="sm"
                          disabled={busy}
                          onClick={() => setConfirmJob(job)}
                        >
                          Cancel
                        </Button>
                      ) : null}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <Progress value={percent} className="w-full">
                    <ProgressLabel>{progressLabel(job)}</ProgressLabel>
                    <ProgressValue />
                  </Progress>
                  <div className="text-muted-foreground flex justify-between text-xs tabular-nums">
                    <span>ETA {eta}</span>
                    <span>Updated {formatWhen(job.updated_at)}</span>
                  </div>
                  {job.phase === "failed" && job.error_message ? (
                    <p className="text-destructive text-sm">{job.error_message}</p>
                  ) : null}
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      <AlertDialog
        open={confirmJob !== null}
        onOpenChange={(open) => {
          if (!open && cancelling === null) setConfirmJob(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel job?</AlertDialogTitle>
            <AlertDialogDescription>
              Stop indexing remaining tracks for{" "}
              <span className="text-foreground font-medium">
                {confirmJob?.name ?? "this job"}
              </span>
              . Tracks already indexed will stay in the catalog.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={cancelling !== null}>
              Keep running
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={cancelling !== null || confirmJob === null}
              onClick={() => {
                if (confirmJob) void cancelJob(confirmJob.id)
              }}
            >
              {cancelling !== null ? "Cancelling…" : "Cancel job"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
