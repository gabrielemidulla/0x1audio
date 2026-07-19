import { NavLink, Outlet } from "react-router"

import { cn } from "~/lib/utils"

const SEGMENTS = [
  { to: "/catalog", label: "Tracks", end: true },
  { to: "/catalog/artists", label: "Artists", end: false },
] as const

export default function CatalogLayout() {
  return (
    <div className="flex max-w-5xl flex-col gap-6">
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-medium tracking-tight">Catalog</h1>
          <p className="text-muted-foreground text-sm leading-relaxed">
            Browse tracks and artists in your library.
          </p>
        </div>
        <nav className="flex gap-1 border-b">
          {SEGMENTS.map((segment) => (
            <NavLink
              key={segment.to}
              to={segment.to}
              end={segment.end}
              className={({ isActive }) =>
                cn(
                  "border-b-2 px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "border-foreground text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )
              }
            >
              {segment.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <Outlet />
    </div>
  )
}
