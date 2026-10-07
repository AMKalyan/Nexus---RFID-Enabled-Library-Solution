import { Download } from "lucide-react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import { download } from "../api/endpoints";

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}

export function Card({ title, children, className = "" }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border border-slate-200 bg-white p-4 shadow-sm ${className}`}>
      {title && <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">{title}</h2>}
      {children}
    </section>
  );
}

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  const styles = {
    primary: "bg-indigo-600 text-white hover:bg-indigo-700",
    secondary: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
    danger: "bg-red-600 text-white hover:bg-red-700",
  }[variant];
  return (
    <button
      {...props}
      className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium disabled:opacity-50 ${styles} ${className}`}
    />
  );
}

export function Input({ label, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className="block text-sm text-slate-700">
      {label}
      <input {...props} className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
    </label>
  );
}

export function StatTile({ label, value, tone = "default" }: { label: string; value: ReactNode; tone?: "default" | "warn" | "alert" }) {
  const color = { default: "text-slate-900", warn: "text-amber-600", alert: "text-red-600" }[tone];
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${color}`}>{value}</div>
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const tone: Record<string, string> = {
    available: "bg-green-100 text-green-800",
    active: "bg-green-100 text-green-800",
    on_loan: "bg-indigo-100 text-indigo-800",
    blocked: "bg-red-100 text-red-800",
    missing: "bg-red-100 text-red-800",
    withdrawn: "bg-slate-200 text-slate-700",
    retired: "bg-slate-200 text-slate-700",
    open: "bg-amber-100 text-amber-800",
    paid: "bg-green-100 text-green-800",
    waived: "bg-slate-200 text-slate-700",
  };
  return <span className={`rounded px-2 py-0.5 text-xs font-medium ${tone[status] ?? "bg-slate-100 text-slate-700"}`}>{status.replace("_", " ")}</span>;
}

export function DataTable({ columns, rows, empty = "No rows" }: { columns: string[]; rows: ReactNode[][]; empty?: string }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50">
          <tr>
            {columns.map((c) => (
              <th key={c} className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
                {c.replace(/_/g, " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-3 py-6 text-center text-slate-400">
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((r, i) => (
              <tr key={i} className="hover:bg-slate-50">
                {r.map((cell, j) => (
                  <td key={j} className="px-3 py-2 text-slate-700">
                    {cell}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export function ExportButtons({ path, name }: { path: string; name: string }) {
  const sep = path.includes("?") ? "&" : "?";
  return (
    <>
      <Button variant="secondary" onClick={() => void download(`${path}${sep}format=csv`, `${name}.csv`)}>
        <Download size={14} aria-hidden /> CSV
      </Button>
      <Button variant="secondary" onClick={() => void download(`${path}${sep}format=pdf`, `${name}.pdf`)}>
        <Download size={14} aria-hidden /> PDF
      </Button>
    </>
  );
}

export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <p role="alert" className="text-sm text-red-600">
      {error instanceof Error ? error.message : "Something went wrong"}
    </p>
  );
}
