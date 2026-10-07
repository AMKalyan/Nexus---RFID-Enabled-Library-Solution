import { useQuery } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { visibleNav } from "./nav";

export function Layout() {
  const { user, permissions, logout } = useAuth();
  const { data: version } = useQuery({
    queryKey: ["version"],
    queryFn: () => api<{ version: string }>("/version"),
  });
  const items = visibleNav(permissions, user?.typ);

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-60 flex-col border-r border-slate-200 bg-white">
        <div className="px-5 py-4 text-lg font-semibold text-indigo-700">Nexus</div>
        <nav className="flex-1 space-y-1 px-2">
          {items.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              end
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm ${
                  isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100"
                }`
              }
            >
              <Icon size={16} aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-200 px-4 py-3 text-xs text-slate-500">
          <div className="mb-2">
            {user?.role} · v{version?.version ?? "…"}
          </div>
          <button onClick={() => void logout()} className="flex items-center gap-2 hover:text-slate-800">
            <LogOut size={14} aria-hidden /> Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
