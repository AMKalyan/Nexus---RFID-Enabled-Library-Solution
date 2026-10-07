import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Card, PageHeader, StatusBadge } from "../components/ui";

type Health = { status: string; checks: Record<string, boolean> };
type Version = { version: string; alembic_rev: string | null; licence: string };

export function HealthPage() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/health"), refetchInterval: 15_000 });
  const version = useQuery({ queryKey: ["version"], queryFn: () => api<Version>("/version") });

  return (
    <div>
      <PageHeader title="System health" />
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Health checks">
          <div className="mb-2 text-sm">
            Overall: <StatusBadge status={health.data?.status === "ok" ? "active" : "blocked"} />
          </div>
          <ul className="space-y-1 text-sm">
            {Object.entries(health.data?.checks ?? {}).map(([name, ok]) => (
              <li key={name}>
                {name}: <span className={ok ? "text-green-700" : "text-red-600"}>{ok ? "ok" : "failing"}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Software version">
          <dl className="grid grid-cols-[150px_1fr] gap-y-1 text-sm">
            <dt className="text-slate-500">Application</dt>
            <dd>{version.data?.version}</dd>
            <dt className="text-slate-500">Database revision</dt>
            <dd>{version.data?.alembic_rev ?? "—"}</dd>
            <dt className="text-slate-500">Licence</dt>
            <dd>{version.data?.licence}</dd>
          </dl>
        </Card>
      </div>
    </div>
  );
}
