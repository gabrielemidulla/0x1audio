import { useEffect, useState } from "react"
import { Navigate, Outlet, useLocation } from "react-router"

import { api, type UserOut } from "~/lib/api"
import { useAudioPlayer } from "~/lib/audio-player"
import { AppSidebar } from "~/components/app-sidebar"
import { FloatingTrackPlayer } from "~/components/floating-track-player"
import { Separator } from "~/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "~/components/ui/sidebar"
import { cn } from "~/lib/utils"

export type AppOutletContext = {
  user: UserOut
}

export default function AppLayout() {
  const [user, setUser] = useState<UserOut | null | undefined>(undefined)
  const [registrationOpen, setRegistrationOpen] = useState<boolean | null>(null)
  const player = useAudioPlayer()
  const location = useLocation()
  const isGraph = location.pathname === "/graph"
  const isChat =
    location.pathname === "/chat" || location.pathname.startsWith("/chat/")

  useEffect(() => {
    void Promise.all([api.v1.me(), api.v1.authStatus()]).then(
      ([meResult, statusResult]) => {
        setUser(meResult.error ? null : (meResult.data ?? null))
        setRegistrationOpen(statusResult.data?.registration_open ?? false)
      },
    )
  }, [])

  if (user === undefined || registrationOpen === null) {
    return (
      <main className="flex min-h-svh items-center justify-center p-6">
        <p className="text-muted-foreground text-sm">Loading…</p>
      </main>
    )
  }

  if (user === null) {
    return <Navigate to={registrationOpen ? "/register" : "/login"} replace />
  }

  return (
    <SidebarProvider className="h-svh max-h-svh overflow-hidden">
      <AppSidebar
        user={user}
        onSignOut={async () => {
          await api.v1.logout()
          setUser(null)
        }}
      />
      <SidebarInset className="min-h-0 flex-1 overflow-hidden">
        <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <span className="text-sm text-muted-foreground">{user.email}</span>
        </header>
        <div
          className={cn(
            "relative flex min-h-0 flex-1 flex-col",
            isGraph || isChat
              ? "overflow-hidden"
              : cn(
                  "gap-6 overflow-x-hidden overflow-y-auto p-6",
                  player.track && "pb-28",
                ),
          )}
        >
          <Outlet context={{ user } satisfies AppOutletContext} />
        </div>
        <FloatingTrackPlayer />
      </SidebarInset>
    </SidebarProvider>
  )
}
