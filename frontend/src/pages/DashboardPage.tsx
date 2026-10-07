import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { reports } from "../api/endpoints";
import { Card, ErrorText, PageHeader, StatTile } from "../components/ui";

export function DashboardPage() {
  const { data, error } = useQuery({ queryKey: ["dashboard"], queryFn: reports.dashboard, refetchInterval: 30_000 });

  return (
    <div>
      <PageHeader title="Dashboard" />
      <ErrorText error={error} />
      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatTile label="Tagged items" value={data.tagged_items.toLocaleString()} />
            <StatTile label="Untagged items" value={data.untagged_items.toLocaleString()} tone={data.untagged_items ? "warn" : "default"} />
            <StatTile label="Active members" value={data.members_active.toLocaleString()} />
            <StatTile label="Blocked members" value={data.members_blocked} tone={data.members_blocked ? "warn" : "default"} />
            <StatTile label="Items on loan" value={data.loans_active} />
            <StatTile label="Overdue loans" value={data.loans_overdue} tone={data.loans_overdue ? "alert" : "default"} />
            <StatTile label="Open fines" value={data.fines_open_total} />
            <StatTile label="Gate alarms today" value={data.gate_alarms_today} tone={data.gate_alarms_today ? "alert" : "default"} />
          </div>
          <div className="mt-4 grid gap-4 lg:grid-cols-[2fr_1fr]">
            <Card title="Loans issued, last 30 days">
              <div className="h-64">
                <ResponsiveContainer>
                  <LineChart data={data.loans_by_day}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} fontSize={11} />
                    <YAxis allowDecimals={false} fontSize={11} />
                    <Tooltip />
                    <Line type="monotone" dataKey="count" stroke="#4f46e5" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card title="Most borrowed titles">
              <div className="h-64">
                <ResponsiveContainer>
                  <BarChart data={data.top_titles} layout="vertical" margin={{ left: 10 }}>
                    <XAxis type="number" allowDecimals={false} fontSize={11} />
                    <YAxis type="category" dataKey="title" width={120} fontSize={10} />
                    <Tooltip />
                    <Bar dataKey="loans" fill="#4f46e5" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Footfall today: {data.footfall_today.in} in / {data.footfall_today.out} out · refreshes every 30 seconds
          </p>
        </>
      )}
    </div>
  );
}
