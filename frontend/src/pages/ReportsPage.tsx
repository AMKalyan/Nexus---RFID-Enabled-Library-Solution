import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { reports } from "../api/endpoints";
import { Button, Card, DataTable, ErrorText, ExportButtons, Input, PageHeader } from "../components/ui";

const REPORTS: Record<string, { label: string; filters: string[] }> = {
  "tagged-items": { label: "Tagged items", filters: ["shelf_code", "tag_status"] },
  members: { label: "Members", filters: ["category", "status"] },
  circulation: { label: "Circulation", filters: ["channel", "member_category"] },
  operators: { label: "Operator activity", filters: [] },
  "rfid-clients": { label: "RFID client activity", filters: ["device_code", "device_type"] },
  fines: { label: "Fines", filters: ["status"] },
  "gate-events": { label: "Gate events", filters: ["alarm", "device_code"] },
};

export function ReportsPage() {
  const [name, setName] = useState("circulation");
  const [form, setForm] = useState<Record<string, string>>({});
  const [applied, setApplied] = useState<Record<string, string>>({});
  const { data, error, isFetching } = useQuery({ queryKey: ["report", name, applied], queryFn: () => reports.run(name, applied) });

  const query = useMemo(() => new URLSearchParams(Object.entries(applied).filter(([, v]) => v)).toString(), [applied]);
  const path = `/reports/${name}${query ? `?${query}` : ""}`;

  return (
    <div>
      <PageHeader title="Reports">
        <ExportButtons path={path} name={`${name}-${new Date().toISOString().slice(0, 10)}`} />
      </PageHeader>
      <Card className="mb-4">
        <div className="grid gap-3 md:grid-cols-[200px_150px_150px_1fr_auto] md:items-end">
          <label className="text-sm text-slate-700">
            Report
            <select
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setForm({});
                setApplied({});
              }}
            >
              {Object.entries(REPORTS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v.label}
                </option>
              ))}
            </select>
          </label>
          <Input label="From" type="date" value={form.from ?? ""} onChange={(e) => setForm({ ...form, from: e.target.value })} />
          <Input label="To" type="date" value={form.to ?? ""} onChange={(e) => setForm({ ...form, to: e.target.value })} />
          <div className="grid grid-cols-2 gap-3">
            {REPORTS[name].filters.map((f) => (
              <Input key={f} label={f.replace(/_/g, " ")} value={form[f] ?? ""} onChange={(e) => setForm({ ...form, [f]: e.target.value })} />
            ))}
          </div>
          <Button onClick={() => setApplied(form)}>Apply</Button>
        </div>
      </Card>
      <ErrorText error={error} />
      <p className="mb-2 text-sm text-slate-500">{isFetching ? "Loading…" : `${data?.rows.length ?? 0} rows`}</p>
      <DataTable
        columns={data?.columns ?? []}
        rows={(data?.rows ?? []).map((r) => r.map((v) => (v === null ? "—" : typeof v === "boolean" ? (v ? "yes" : "no") : String(v))))}
      />
    </div>
  );
}
