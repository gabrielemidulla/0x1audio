import { useState } from "react"
import {
  CaretUpDown,
  ChatCircle,
  Graph,
  House,
  MusicNotes,
  Playlist,
  Queue,
  SignOut,
  Users,
} from "@phosphor-icons/react"
import { Link, useLocation } from "react-router"

import type { UserOut } from "~/lib/api"
import { Button } from "~/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "~/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "~/components/ui/dropdown-menu"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "~/components/ui/sidebar"

type AppSidebarProps = {
  user: UserOut
  onSignOut: () => void | Promise<void>
}

export function AppSidebar({ user, onSignOut }: AppSidebarProps) {
  const { pathname } = useLocation()
  const [signOutOpen, setSignOutOpen] = useState(false)
  const [signingOut, setSigningOut] = useState(false)

  return (
    <>
      <Sidebar collapsible="icon" variant="inset">
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton size="lg" render={<Link to="/" />}>
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <MusicNotes className="size-4" weight="fill" />
                </div>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-medium">Tunelink</span>
                  <span className="truncate text-xs text-muted-foreground">
                    {user.role === "master" ? "Master" : "User"}
                  </span>
                </div>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Library</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton
                    isActive={pathname === "/"}
                    tooltip="Home"
                    render={<Link to="/" />}
                  >
                    <House />
                    <span>Home</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem>
                  <SidebarMenuButton
                    isActive={pathname === "/catalog"}
                    tooltip="Catalog"
                    render={<Link to="/catalog" />}
                  >
                    <MusicNotes />
                    <span>Catalog</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem>
                  <SidebarMenuButton
                    isActive={pathname.startsWith("/playlists")}
                    tooltip="Playlists"
                    render={<Link to="/playlists" />}
                  >
                    <Playlist />
                    <span>Playlists</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem>
                  <SidebarMenuButton
                    isActive={pathname === "/graph"}
                    tooltip="Graph"
                    render={<Link to="/graph" />}
                  >
                    <Graph />
                    <span>Graph</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem>
                  <SidebarMenuButton
                    isActive={pathname.startsWith("/chat")}
                    tooltip="Chat"
                    render={<Link to="/chat" />}
                  >
                    <ChatCircle />
                    <span>Chat</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem>
                  <SidebarMenuButton
                    isActive={pathname === "/jobs"}
                    tooltip="Jobs"
                    render={<Link to="/jobs" />}
                  >
                    <Queue />
                    <span>Jobs</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                {user.role === "master" ? (
                  <SidebarMenuItem>
                    <SidebarMenuButton
                      isActive={pathname === "/users"}
                      tooltip="Users"
                      render={<Link to="/users" />}
                    >
                      <Users />
                      <span>Users</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ) : null}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>

        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              <DropdownMenu>
                <DropdownMenuTrigger
                  render={
                    <SidebarMenuButton
                      size="lg"
                      className="aria-expanded:bg-sidebar-accent"
                    />
                  }
                >
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-medium">{user.email}</span>
                    <span className="truncate text-xs text-muted-foreground">
                      {user.role === "master" ? "Master" : "User"}
                    </span>
                  </div>
                  <CaretUpDown className="ml-auto size-4" />
                </DropdownMenuTrigger>
                <DropdownMenuContent side="top" align="start" className="w-56">
                  <DropdownMenuItem
                    variant="destructive"
                    onClick={() => setSignOutOpen(true)}
                  >
                    <SignOut />
                    Sign out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>

        <SidebarRail />
      </Sidebar>

      <Dialog open={signOutOpen} onOpenChange={setSignOutOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Sign out?</DialogTitle>
            <DialogDescription>
              You will need to sign in again to use Tunelink.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" />} disabled={signingOut}>
              Cancel
            </DialogClose>
            <Button
              variant="destructive"
              disabled={signingOut}
              onClick={async () => {
                setSigningOut(true)
                try {
                  await onSignOut()
                } finally {
                  setSigningOut(false)
                  setSignOutOpen(false)
                }
              }}
            >
              {signingOut ? "Signing out…" : "Sign out"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
