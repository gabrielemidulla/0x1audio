import { useEffect, useState } from "react"
import { Link, useNavigate, useOutletContext } from "react-router"
import { Graph, MusicNotes, Playlist, Queue } from "@phosphor-icons/react"

import type { AppOutletContext } from "~/routes/_app"
import { ChatPrompter } from "~/components/chat-prompter"
import { ChatTrackRow } from "~/components/chat-track-row"
import { GreetingStage } from "~/components/greeting-hero"
import { Reveal } from "~/components/reveal"
import { Skeleton } from "~/components/ui/skeleton"
import {
  hasDashboardEntered,
  markDashboardEntered,
  readDashboardSnapshot,
  writeDashboardSnapshot,
} from "~/lib/dashboard-cache"
import { api, type JobOut, type TrackOut } from "~/lib/api"

const NAV_LINKS = [
  {
    to: "/catalog",
    title: "Catalog",
    description: "Browse and upload tracks",
    Icon: MusicNotes,
  },
  {
    to: "/playlists",
    title: "Playlists",
    description: "Your private track lists",
    Icon: Playlist,
  },
  {
    to: "/graph",
    title: "Graph",
    description: "Explore sound-alike neighborhoods",
    Icon: Graph,
  },
] as const

const CARD_DELAYS = ["delay-0", "delay-100", "delay-200", "delay-300"] as const

function DashboardSkeleton() {
  return (
    <>
      <section className="relative z-10 grid gap-3 sm:grid-cols-2">
        {Array.from({ length: 4 }, (_, i) => (
          <div
            key={i}
            className="flex flex-col gap-2 rounded-xl border bg-card px-4 py-3"
          >
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-3 w-36" />
          </div>
        ))}
      </section>
      <section className="flex flex-col gap-2">
        <Skeleton className="h-4 w-28" />
        <ul className="flex flex-col gap-2">
          {Array.from({ length: 4 }, (_, i) => (
            <li key={i} className="flex items-center gap-3 px-1 py-1.5">
              <Skeleton className="size-10 shrink-0 rounded-md" />
              <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-3 w-28" />
              </div>
            </li>
          ))}
        </ul>
      </section>
    </>
  )
}

function countPendingJobs(jobs: JobOut[]): number {
  return jobs.filter(
    (job) =>
      job.phase === "queued" ||
      job.phase === "importing" ||
      job.phase === "indexing",
  ).length
}

export default function DashboardPage() {
  const { user } = useOutletContext<AppOutletContext>()
  const navigate = useNavigate()
  const cached = readDashboardSnapshot()
  const alreadyEntered = hasDashboardEntered()

  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [recent, setRecent] = useState<TrackOut[] | null>(
    () => cached?.recent ?? null,
  )
  const [pendingJobs, setPendingJobs] = useState<number | null>(
    () => cached?.pendingJobs ?? null,
  )
  const [heroIn, setHeroIn] = useState(alreadyEntered)
  const [panelMounted, setPanelMounted] = useState(
    () => alreadyEntered && cached != null,
  )
  const [panelIn, setPanelIn] = useState(
    () => alreadyEntered && cached != null,
  )

  useEffect(() => {
    let cancelled = false
    void Promise.all([
      api.v1.listTracks({ query: { status: "ready", limit: 8 } }),
      api.v1.listJobs(),
    ]).then(([tracksResult, jobsResult]) => {
      if (cancelled) return
      const nextRecent = tracksResult.data?.items ?? []
      const nextPending = jobsResult.data
        ? countPendingJobs(jobsResult.data)
        : 0
      setRecent(nextRecent)
      setPendingJobs(nextPending)
      writeDashboardSnapshot({ recent: nextRecent, pendingJobs: nextPending })
    })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (alreadyEntered) {
      setHeroIn(true)
      return
    }
    const timer = window.setTimeout(() => setHeroIn(true), 50)
    return () => window.clearTimeout(timer)
  }, [alreadyEntered])

  const ready = recent !== null && pendingJobs !== null

  useEffect(() => {
    if (!ready) return

    if (alreadyEntered) {
      setPanelMounted(true)
      setPanelIn(true)
      return
    }

    let frame = 0
    const timer = window.setTimeout(() => {
      setPanelMounted(true)
      setPanelIn(false)
      frame = window.requestAnimationFrame(() => {
        frame = window.requestAnimationFrame(() => {
          setPanelIn(true)
          markDashboardEntered()
        })
      })
    }, 400)

    return () => {
      window.clearTimeout(timer)
      window.cancelAnimationFrame(frame)
    }
  }, [ready, alreadyEntered])

  const jobsLabel =
    pendingJobs != null && pendingJobs > 0
      ? `${pendingJobs} active`
      : "Indexing status"

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-10 py-8">
      <section className="flex flex-col items-center gap-6 pt-8 text-center">
        <Reveal visible={heroIn} className="w-full max-w-xl">
          <GreetingStage
            name={user?.display_name}
            email={user?.email}
            loading={!user}
          >
            <ChatPrompter
              className="w-full"
              autoFocus
              disabled={busy || !user}
              onSubmit={async (message) => {
                setBusy(true)
                setError(null)
                const { data, error: apiError } = await api.v1.createChat({
                  body: { message },
                })
                setBusy(false)
                if (apiError || !data) {
                  setError("Could not start chat")
                  return
                }
                void navigate(`/chat/${data.id}`, { state: { seed: data } })
              }}
            />
          </GreetingStage>
        </Reveal>
        {error ? <p className="text-destructive text-sm">{error}</p> : null}
      </section>

      {!panelMounted ? (
        <DashboardSkeleton />
      ) : (
        <>
          <section className="relative z-10 grid gap-3 sm:grid-cols-2">
            {NAV_LINKS.map(({ to, title, description, Icon }, index) => (
              <Reveal key={to} visible={panelIn} delayClass={CARD_DELAYS[index]}>
                <Link
                  to={to}
                  className="hover:bg-muted/60 flex flex-col gap-1 rounded-xl border bg-card px-4 py-3 text-left transition-colors"
                >
                  <span className="flex items-center gap-2 text-sm font-medium">
                    <Icon className="size-4" />
                    {title}
                  </span>
                  <span className="text-muted-foreground text-xs">
                    {description}
                  </span>
                </Link>
              </Reveal>
            ))}
            <Reveal visible={panelIn} delayClass={CARD_DELAYS[3]}>
              <Link
                to="/jobs"
                className="hover:bg-muted/60 flex flex-col gap-1 rounded-xl border bg-card px-4 py-3 text-left transition-colors"
              >
                <span className="flex items-center gap-2 text-sm font-medium">
                  <Queue className="size-4" />
                  Jobs
                </span>
                <span className="text-muted-foreground text-xs">{jobsLabel}</span>
              </Link>
            </Reveal>
          </section>

          {recent && recent.length > 0 ? (
            <Reveal visible={panelIn} delayClass="delay-400">
              <section className="flex flex-col gap-2">
                <h2 className="text-sm font-medium">Recently ready</h2>
                <ul className="flex flex-col gap-0.5">
                  {recent.map((track) => (
                    <li key={track.id}>
                      <ChatTrackRow track={track} />
                    </li>
                  ))}
                </ul>
              </section>
            </Reveal>
          ) : null}
        </>
      )}
    </div>
  )
}
