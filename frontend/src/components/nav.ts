import {
  Activity,
  BarChart3,
  BookMarked,
  BookOpen,
  ClipboardList,
  DoorOpen,
  FileSpreadsheet,
  LayoutDashboard,
  Library,
  Radio,
  ScanLine,
  Settings,
  ShieldCheck,
  Tag,
  Users,
  type LucideIcon,
} from "lucide-react";

export type NavItem = { path: string; label: string; icon: LucideIcon; perm: string; patronOnly?: boolean };

// The server enforces every permission; the menu only hides what a role cannot use.
export const NAV: NavItem[] = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard, perm: "reports.read" },
  { path: "/circulation", label: "Circulation desk", icon: ScanLine, perm: "circulation.checkout" },
  { path: "/catalogue", label: "Catalogue", icon: BookOpen, perm: "catalog.write" },
  { path: "/tagging", label: "Tagging", icon: Tag, perm: "tagging.write" },
  { path: "/inventory", label: "Inventory", icon: ClipboardList, perm: "inventory.write" },
  { path: "/gate", label: "Gate monitor", icon: DoorOpen, perm: "gate.read" },
  { path: "/members", label: "Members", icon: Users, perm: "members.read" },
  { path: "/reports", label: "Reports", icon: BarChart3, perm: "reports.read" },
  { path: "/devices", label: "Devices", icon: Radio, perm: "devices.read" },
  { path: "/migration", label: "Migration", icon: FileSpreadsheet, perm: "migration.run" },
  { path: "/audit", label: "Audit log", icon: ShieldCheck, perm: "audit.read" },
  { path: "/admin", label: "Administration", icon: Settings, perm: "admin.users.write" },
  { path: "/health", label: "System health", icon: Activity, perm: "admin.health" },
  { path: "/my-loans", label: "My loans", icon: BookMarked, perm: "catalog.read", patronOnly: true },
  { path: "/opac", label: "OPAC", icon: Library, perm: "catalog.read" },
];

export function visibleNav(permissions: Set<string>, typ: string | undefined): NavItem[] {
  return NAV.filter((n) => permissions.has(n.perm) && (!n.patronOnly || typ === "patron"));
}
