import { useEffect, useState } from "react"
import { Navigate, Outlet, useLocation } from "react-router"

import { api, type UserOut } from "~/lib/api"
import { AppSidebar } from "~/components/app-sidebar"
import { FloatingTrackPlayer } from "~/components/floating-track-player"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "~/components/ui/sidebar"
import { cn } from "~/lib/utils"

export type AppOutletContext = {
  user: UserOut | null
  setUser: (user: UserOut) => void
}

function needsOnboarding(user: UserOut): boolean {
  return Boolean(user.must_change_password) || !user.display_name?.trim()
}

export default function AppLayout() {
  const [user, setUser] = useState<UserOut | null | undefined>(undefined)
  const [registrationOpen, setRegistrationOpen] = useState<boolean | null>(null)
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

  // Auth resolved and not signed in → leave the app shell.
  if (user === null && registrationOpen !== null) {
    return <Navigate to={registrationOpen ? "/register" : "/login"} replace />
  }

  if (user && needsOnboarding(user)) {
    return <Navigate to="/onboarding" replace />
  }

  // Show chrome immediately; skeleton only the bits that need user/data.
  return (
    <SidebarProvider className="h-svh max-h-svh overflow-hidden">
      <AppSidebar
        user={user ?? null}
        onUserChange={setUser}
        onSignOut={async () => {
          await api.v1.logout()
          setUser(null)
        }}
      />
      <SidebarInset className="min-h-0 flex-1 overflow-hidden">
        <header className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger className="-ml-1" />
        </header>
        <div
          className={cn(
            "relative flex min-h-0 flex-1 flex-col",
            isGraph || isChat
              ? "overflow-hidden"
              : "gap-6 overflow-x-hidden overflow-y-auto p-6",
          )}
        >
          <Outlet
            context={
              {
                user: user ?? null,
                setUser,
              } satisfies AppOutletContext
            }
          />
        </div>
      </SidebarInset>
      <FloatingTrackPlayer />
    </SidebarProvider>
  )
}
