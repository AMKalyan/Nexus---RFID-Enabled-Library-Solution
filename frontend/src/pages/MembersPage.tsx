import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CreditCard } from "lucide-react";
import { useState } from "react";
import { ApiError } from "../api/client";
import { download, members } from "../api/endpoints";
import { RequirePermission } from "../auth/AuthContext";
import { RefusalBanner } from "../components/RefusalBanner";
import { Button, Card, DataTable, Input, PageHeader, StatusBadge } from "../components/ui";

const EMPTY = { card_no: "", full_name: "", email: "", phone: "", category_code: "UG" };

export function MembersPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState<ApiError | null>(null);

  const list = useQuery({ queryKey: ["members", search], queryFn: () => members.search(search) });
  const selected = useQuery({ queryKey: ["member", selectedId], queryFn: () => members.get(selectedId!), enabled: !!selectedId });
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["members"] });
    void qc.invalidateQueries({ queryKey: ["member"] });
  };
  const create = useMutation({
    mutationFn: () => members.create({ ...form, email: form.email || null, phone: form.phone || null }),
    onSuccess: (m) => {
      setForm(EMPTY);
      setError(null);
      setSelectedId(m.id);
      refresh();
    },
    onError: (e) => setError(e as ApiError),
  });
  const toggleBlock = useMutation({
    mutationFn: async () => {
      const m = selected.data!;
      if (m.status === "blocked") return members.unblock(m.id);
      const reason = window.prompt("Reason for blocking this member?");
      if (!reason) throw new ApiError("CANCELLED", "Cancelled", 0);
      return members.block(m.id, reason);
    },
    onSuccess: refresh,
    onError: (e) => (e as ApiError).code !== "CANCELLED" && setError(e as ApiError),
  });

  const m = selected.data;
  return (
    <div>
      <PageHeader title="Members" />
      {error && <div className="mb-3"><RefusalBanner code={error.code} message={error.message} /></div>}
      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <Card title="Find">
          <form
            className="mb-3 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setSearch(q);
            }}
          >
            <input className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="Card number or name" value={q} onChange={(e) => setQ(e.target.value)} />
            <Button type="submit">Search</Button>
          </form>
          <DataTable
            columns={["card", "name", "category", "status", ""]}
            rows={(list.data ?? []).map((x) => [
              x.card_no,
              x.full_name,
              x.category_code,
              <StatusBadge status={x.status} />,
              <Button variant="secondary" onClick={() => setSelectedId(x.id)}>
                Open
              </Button>,
            ])}
          />
        </Card>
        <div className="space-y-4">
          {m && (
            <Card title={m.full_name}>
              <dl className="grid grid-cols-[110px_1fr] gap-y-1 text-sm">
                <dt className="text-slate-500">Card</dt>
                <dd>{m.card_no}</dd>
                <dt className="text-slate-500">Email</dt>
                <dd>{m.email ?? "—"}</dd>
                <dt className="text-slate-500">Phone</dt>
                <dd>{m.phone ?? "—"}</dd>
                <dt className="text-slate-500">Status</dt>
                <dd>
                  <StatusBadge status={m.status} /> {m.block_reason && <span className="text-red-600">{m.block_reason}</span>}
                </dd>
                <dt className="text-slate-500">Loans</dt>
                <dd>
                  {m.open_loans} / {m.max_items}
                </dd>
                <dt className="text-slate-500">Open fines</dt>
                <dd>
                  {m.open_fines} (limit {m.fine_limit})
                </dd>
              </dl>
              <div className="mt-3 flex gap-2">
                <RequirePermission perm="members.block">
                  <Button variant={m.status === "blocked" ? "secondary" : "danger"} onClick={() => toggleBlock.mutate()}>
                    {m.status === "blocked" ? "Unblock" : "Block"}
                  </Button>
                </RequirePermission>
                <RequirePermission perm="members.write">
                  <Button variant="secondary" onClick={() => void download(`/members/${m.id}/card.pdf`, `card-${m.card_no}.pdf`)}>
                    <CreditCard size={14} aria-hidden /> Print card
                  </Button>
                </RequirePermission>
              </div>
            </Card>
          )}
          <RequirePermission perm="members.write">
            <Card title="New member">
              <form
                className="grid gap-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  create.mutate();
                }}
              >
                <div className="grid grid-cols-2 gap-3">
                  <Input label="Card number" required value={form.card_no} onChange={(e) => setForm({ ...form, card_no: e.target.value })} />
                  <label className="text-sm text-slate-700">
                    Category
                    <select className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" value={form.category_code} onChange={(e) => setForm({ ...form, category_code: e.target.value })}>
                      {["UG", "PG", "FAC", "STAFF"].map((c) => (
                        <option key={c}>{c}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <Input label="Full name" required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
                <Input label="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
                <Input label="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                <Button type="submit" disabled={create.isPending}>
                  Create member
                </Button>
              </form>
            </Card>
          </RequirePermission>
        </div>
      </div>
    </div>
  );
}
