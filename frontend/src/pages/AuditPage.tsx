import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { admin, fmtDate } from "../api/endpoints";
import { Button, Card, DataTable, ErrorText, Input, PageHeader } from "../components/ui";

export function AuditPage() {
  const [form, setForm] = useState({ action: "", from: "", to: "" });
  const [applied, setApplied] = useState(form);
  const [page, setPage] = useState(1);
  const { data, error } = useQuery({
    queryKey: ["audit", applied, page],
    queryFn: () => admin.audit({ ...applied, page, size: 50 }),
  });

  return (
    <div>
      <PageHeader title="Audit log" />
      <Card className="mb-4">
        <form
          className="grid gap-3 md:grid-cols-[1fr_160px_160px_auto] md:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setApplied(form);
          }}
        >
          <Input label="Action starts with" placeholder="circulation." value={form.action} onChange={(e) => setForm({ ...form, action: e.target.value })} />
          <Input label="From" type="date" value={form.from} onChange={(e) => setForm({ ...form, from: e.target.value })} />
          <Input label="To" type="date" value={form.to} onChange={(e) => setForm({ ...form, to: e.target.value })} />
          <Button type="submit">Filter</Button>
        </form>
      </Card>
      <ErrorText error={error} />
      <p className="mb-2 text-sm text-slate-500">{data?.total ?? 0} entries</p>
      <DataTable
        columns={["time", "actor", "action", "entity", "details", "ip"]}
        rows={(data?.items ?? []).map((a) => [
          fmtDate(a.occurred_at),
          `${a.actor_type}${a.actor_id ? ` ${a.actor_id.slice(0, 8)}` : ""}`,
          <span className="font-mono text-xs">{a.action}</span>,
          `${a.entity_type}${a.entity_id ? ` ${a.entity_id.slice(0, 12)}` : ""}`,
          <span className="font-mono text-xs text-slate-500">{JSON.stringify(a.details)}</span>,
          a.ip ?? "—",
        ])}
      />
      <div className="mt-3 flex gap-2">
        <Button variant="secondary" disabled={page === 1} onClick={() => setPage(page - 1)}>
          Previous
        </Button>
        <Button variant="secondary" disabled={!data || page * 50 >= data.total} onClick={() => setPage(page + 1)}>
          Next
        </Button>
      </div>
    </div>
  );
}
