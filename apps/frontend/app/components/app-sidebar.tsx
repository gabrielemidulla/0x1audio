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
  User as UserIcon,
  Users,
} from "@phosphor-icons/react"
import { Link, useLocation } from "react-router"

import { AccountDialog } from "~/components/account-dialog"
import { SlidingHoverList } from "~/components/sliding-hover-list"
import type { UserOut } from "~/lib/api"
import { userAvatarUrl } from "~/lib/api"
import { Avatar, AvatarFallback, AvatarImage } from "~/components/ui/avatar"
import { Button } from "~/components/ui/button"
import { Skeleton } from "~/components/ui/skeleton"
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
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
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
  user: UserOut | null
  onUserChange: (user: UserOut) => void
  onSignOut: () => void | Promise<void>
}

export function AppSidebar({ user, onUserChange, onSignOut }: AppSidebarProps) {
  const { pathname } = useLocation()
  const [signOutOpen, setSignOutOpen] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const primaryLabel = user?.display_name?.trim() || "Account"

  return (
    <>
      <Sidebar collapsible="icon" variant="inset">
        <SidebarHeader>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton
                size="lg"
                className="h-auto gap-0 overflow-visible px-2 py-2 hover:bg-transparent active:bg-transparent group-data-[collapsible=icon]:size-8! group-data-[collapsible=icon]:p-1!"
                render={<Link to="/" aria-label="0x1audio home" />}
              >
                <img
                  src="/logo.svg"
                  alt="0x1audio"
                  className="h-5 w-auto max-w-none dark:invert group-data-[collapsible=icon]:h-4 group-data-[collapsible=icon]:w-4 group-data-[collapsible=icon]:object-left group-data-[collapsible=icon]:object-cover"
                />
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Library</SidebarGroupLabel>
            <SidebarGroupContent>
              <SlidingHoverList
                as="ul"
                data-slot="sidebar-menu"
                data-sidebar="menu"
                className="flex w-full min-w-0 flex-col gap-0.5"
                indicatorClassName="rounded-md bg-sidebar-accent"
              >
                <SidebarMenuItem data-sliding-item className="relative z-[1]">
                  <SidebarMenuButton
                    isActive={pathname === "/"}
                    tooltip="Home"
                    className="hover:bg-transparent active:bg-transparent data-open:hover:bg-transparent"
                    render={<Link to="/" />}
                  >
                    <House />
                    <span>Home</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem data-sliding-item className="relative z-[1]">
                  <SidebarMenuButton
                    isActive={pathname === "/catalog"}
                    tooltip="Catalog"
                    className="hover:bg-transparent active:bg-transparent data-open:hover:bg-transparent"
                    render={<Link to="/catalog" />}
                  >
                    <MusicNotes />
                    <span>Catalog</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem data-sliding-item className="relative z-[1]">
                  <SidebarMenuButton
                    isActive={pathname.startsWith("/playlists")}
                    tooltip="Playlists"
                    className="hover:bg-transparent active:bg-transparent data-open:hover:bg-transparent"
                    render={<Link to="/playlists" />}
                  >
                    <Playlist />
                    <span>Playlists</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem data-sliding-item className="relative z-[1]">
                  <SidebarMenuButton
                    isActive={pathname === "/graph"}
                    tooltip="Graph"
                    className="hover:bg-transparent active:bg-transparent data-open:hover:bg-transparent"
                    render={<Link to="/graph" />}
                  >
                    <Graph />
                    <span>Graph</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem data-sliding-item className="relative z-[1]">
                  <SidebarMenuButton
                    isActive={pathname.startsWith("/chat")}
                    tooltip="Chat"
                    className="hover:bg-transparent active:bg-transparent data-open:hover:bg-transparent"
                    render={<Link to="/chat" />}
                  >
                    <ChatCircle />
                    <span>Chat</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                <SidebarMenuItem data-sliding-item className="relative z-[1]">
                  <SidebarMenuButton
                    isActive={pathname === "/jobs"}
                    tooltip="Jobs"
                    className="hover:bg-transparent active:bg-transparent data-open:hover:bg-transparent"
                    render={<Link to="/jobs" />}
                  >
                    <Queue />
                    <span>Jobs</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
                {user?.role === "master" ? (
                  <SidebarMenuItem data-sliding-item className="relative z-[1]">
                    <SidebarMenuButton
                      isActive={pathname === "/users"}
                      tooltip="Users"
                      className="hover:bg-transparent active:bg-transparent data-open:hover:bg-transparent"
                      render={<Link to="/users" />}
                    >
                      <Users />
                      <span>Users</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ) : null}
              </SlidingHoverList>
            </SidebarGroupContent>
          </SidebarGroup>
        </SidebarContent>

        <SidebarFooter>
          <SidebarMenu>
            <SidebarMenuItem>
              {user ? (
                <DropdownMenu>
                  <DropdownMenuTrigger
                    render={
                      <SidebarMenuButton
                        size="lg"
                        className="aria-expanded:bg-sidebar-accent"
                      />
                    }
                  >
                    <Avatar className="size-8 rounded-lg data-[size=default]:size-8">
                      {user.has_avatar ? (
                        <AvatarImage src={userAvatarUrl(user.id)} alt="" />
                      ) : null}
                      <AvatarFallback className="rounded-lg">
                        <UserIcon className="size-4" />
                      </AvatarFallback>
                    </Avatar>
                    <div className="grid min-w-0 flex-1 text-left text-sm leading-tight">
                      <span className="truncate font-medium">{primaryLabel}</span>
                      <span className="text-muted-foreground truncate text-xs blur-[5px] select-none">
                        {user.email}
                      </span>
                    </div>
                    <CaretUpDown className="ml-auto size-4" />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent side="top" align="start" className="w-56">
                    <DropdownMenuGroup>
                      <DropdownMenuLabel className="font-normal">
                        <div className="flex flex-col gap-0.5">
                          <span className="truncate text-sm font-medium">
                            {primaryLabel}
                          </span>
                          <span className="text-muted-foreground truncate text-xs">
                            {user.email}
                          </span>
                        </div>
                      </DropdownMenuLabel>
                    </DropdownMenuGroup>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => setAccountOpen(true)}>
                      <UserIcon />
                      Account
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      variant="destructive"
                      onClick={() => setSignOutOpen(true)}
                    >
                      <SignOut />
                      Sign out
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : (
                <div className="flex items-center gap-2 px-2 py-2">
                  <Skeleton className="size-8 shrink-0 rounded-lg" />
                  <div className="grid min-w-0 flex-1 gap-1.5">
                    <Skeleton className="h-3.5 w-24" />
                    <Skeleton className="h-3 w-32" />
                  </div>
                </div>
              )}
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>

        <SidebarRail />
      </Sidebar>

      {user ? (
        <AccountDialog
          user={user}
          open={accountOpen}
          onOpenChange={setAccountOpen}
          onUserChange={onUserChange}
        />
      ) : null}

      <Dialog open={signOutOpen} onOpenChange={setSignOutOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Sign out?</DialogTitle>
            <DialogDescription>
              You will need to sign in again to use 0x1audio.
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
