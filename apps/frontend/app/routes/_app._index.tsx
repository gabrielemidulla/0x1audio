import { useEffect, useState } from "react"
import { Link, useNavigate, useOutletContext } from "react-router"
import { Graph, MusicNotes, Playlist, Queue } from "@phosphor-icons/react"

import type { AppOutletContext } from "~/routes/_app"
import { ChatPrompter } from "~/components/chat-prompter"
import { ChatTrackRow } from "~/components/chat-track-row"
import { GreetingStage } from "~/components/greeting-hero"
import { api, type JobOut, type TrackOut } from "~/lib/api"

export default function DashboardPage() {
  const { user } = useOutletContext<AppOutletContext>()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [recent, setRecent] = useState<TrackOut[]>([])
  const [pendingJobs, setPendingJobs] = useState<number | null>(null)

  useEffect(() => {
    void Promise.all([
      api.v1.listTracks({ query: { status: "ready", limit: 8 } }),
      api.v1.listJobs(),
    ]).then(([tracksResult, jobsResult]) => {
      if (tracksResult.data) {
        setRecent(tracksResult.data)
      }
      if (jobsResult.data) {
        setPendingJobs(
          jobsResult.data.filter(
            (job: JobOut) =>
              job.phase === "queued" ||
              job.phase === "importing" ||
              job.phase === "indexing",
          ).length,
        )
      }
    })
  }, [])

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-10 py-8">
      <section className="flex flex-col items-center gap-6 pt-8 text-center">
        <GreetingStage email={user.email}>
          <ChatPrompter
            className="w-full"
            autoFocus
            disabled={busy}
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
        {error ? <p className="text-destructive text-sm">{error}</p> : null}
      </section>

      <section className="relative z-10 grid gap-3 sm:grid-cols-2">
        <Link
          to="/catalog"
          className="hover:bg-muted/60 flex flex-col gap-1 rounded-xl border bg-card px-4 py-3 text-left transition-colors"
        >
          <span className="flex items-center gap-2 text-sm font-medium">
            <MusicNotes className="size-4" />
            Catalog
          </span>
          <span className="text-muted-foreground text-xs">
            Browse and upload tracks
          </span>
        </Link>
        <Link
          to="/playlists"
          className="hover:bg-muted/60 flex flex-col gap-1 rounded-xl border bg-card px-4 py-3 text-left transition-colors"
        >
          <span className="flex items-center gap-2 text-sm font-medium">
            <Playlist className="size-4" />
            Playlists
          </span>
          <span className="text-muted-foreground text-xs">
            Your private track lists
          </span>
        </Link>
        <Link
          to="/graph"
          className="hover:bg-muted/60 flex flex-col gap-1 rounded-xl border bg-card px-4 py-3 text-left transition-colors"
        >
          <span className="flex items-center gap-2 text-sm font-medium">
            <Graph className="size-4" />
            Graph
          </span>
          <span className="text-muted-foreground text-xs">
            Explore sound-alike neighborhoods
          </span>
        </Link>
        <Link
          to="/jobs"
          className="hover:bg-muted/60 flex flex-col gap-1 rounded-xl border bg-card px-4 py-3 text-left transition-colors"
        >
          <span className="flex items-center gap-2 text-sm font-medium">
            <Queue className="size-4" />
            Jobs
          </span>
          <span className="text-muted-foreground text-xs">
            {pendingJobs != null && pendingJobs > 0
              ? `${pendingJobs} active`
              : "Indexing status"}
          </span>
        </Link>
      </section>

      {recent.length > 0 ? (
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
      ) : null}
    </div>
  )
}
