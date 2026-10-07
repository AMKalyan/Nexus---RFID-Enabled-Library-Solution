import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError } from "../api/client";
import { admin, fmtDate, type Policy } from "../api/endpoints";
import { RefusalBanner } from "../components/RefusalBanner";
import { Button, Card, DataTable, Input, PageHeader, StatusBadge } from "../components/ui";

const ROLES = ["Admin", "Librarian", "CirculationClerk", "Auditor"];
const EMPTY_USER = { username: "", display_name: "", role: "CirculationClerk", password: "", smartcard_uid: "" };

export function AdminPage() {
  const qc = useQueryClient();
  const [error, setError] = useState<ApiError | null>(null);
  const [form, setForm] = useState(EMPTY_USER);
  const users = useQuery({ queryKey: ["users"], queryFn: admin.users });
  const policies = useQuery({ queryKey: ["policies"], queryFn: admin.policies });
  const onError = (e: unknown) => setError(e as ApiError);
  const create = useMutation({
    mutationFn: () => admin.createUser({ ...form, smartcard_uid: form.smartcard_uid || null }),
    onSuccess: () => {
      setForm(EMPTY_USER);
      setError(null);
      void qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError,
  });
  const toggle = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) => admin.updateUser(id, { is_active: active }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["users"] }),
    onError,
  });
  const savePolicy = useMutation({
    mutationFn: (p: Policy) =>
      admin.updatePolicy(p.category_code, {
        loan_days: p.loan_days,
        max_items: p.max_items,
        max_renewals: p.max_renewals,
        fine_per_day: p.fine_per_day,
        fine_limit: p.fine_limit,
        can_borrow_reference: p.can_borrow_reference,
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["policies"] }),
    onError,
  });

  return (
    <div>
      <PageHeader title="Administration" />
      {error && <div className="mb-3"><RefusalBanner code={error.code} message={error.message} /></div>}
      <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
        <Card title="Staff users">
          <DataTable
            columns={["username", "name", "role", "card", "last sign-in", "status", ""]}
            rows={(users.data ?? []).map((u) => [
              u.username,
              u.display_name,
              u.role,
              u.has_smartcard ? "yes" : "—",
              fmtDate(u.last_login_at),
              <StatusBadge status={u.is_active ? "active" : "withdrawn"} />,
              <Button variant="secondary" onClick={() => toggle.mutate({ id: u.id, active: !u.is_active })}>
                {u.is_active ? "Deactivate" : "Activate"}
              </Button>,
            ])}
          />
        </Card>
        <Card title="New staff user">
          <form
            className="grid gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate();
            }}
          >
            <div className="grid grid-cols-2 gap-3">
              <Input label="Username" required value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
              <label className="text-sm text-slate-700">
                Role
                <select className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  {ROLES.map((r) => (
                    <option key={r}>{r}</option>
                  ))}
                </select>
              </label>
            </div>
            <Input label="Display name" required value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
            <Input label="Initial password (12+ characters, letter and digit)" type="password" required autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            <Input label="Smart-card UID (optional)" value={form.smartcard_uid} onChange={(e) => setForm({ ...form, smartcard_uid: e.target.value })} />
            <Button type="submit" disabled={create.isPending}>
              Create user
            </Button>
          </form>
        </Card>
      </div>
      <Card title="Circulation policies" className="mt-4">
        <PolicyTable policies={policies.data ?? []} onSave={(p) => savePolicy.mutate(p)} />
      </Card>
    </div>
  );
}

function PolicyTable({ policies, onSave }: { policies: Policy[]; onSave: (p: Policy) => void }) {
  const [edits, setEdits] = useState<Record<string, Policy>>({});
  const value = (p: Policy) => edits[p.category_code] ?? p;
  const set = (p: Policy, field: keyof Policy, v: string | boolean) =>
    setEdits({ ...edits, [p.category_code]: { ...value(p), [field]: typeof v === "boolean" ? v : field.startsWith("fine") ? v : Number(v) } });
  const num = (p: Policy, field: keyof Policy) => (
    <input className="w-20 rounded border border-slate-300 px-2 py-1 text-sm" value={String(value(p)[field])} onChange={(e) => set(p, field, e.target.value)} />
  );
  return (
    <DataTable
      columns={["category", "loan days", "max items", "max renewals", "fine / day", "fine limit", "reference", ""]}
      rows={policies.map((p) => [
        `${p.category_code} · ${p.name}`,
        num(p, "loan_days"),
        num(p, "max_items"),
        num(p, "max_renewals"),
        num(p, "fine_per_day"),
        num(p, "fine_limit"),
        <input type="checkbox" checked={value(p).can_borrow_reference} onChange={(e) => set(p, "can_borrow_reference", e.target.checked)} />,
        <Button variant="secondary" disabled={!edits[p.category_code]} onClick={() => onSave(value(p))}>
          Save
        </Button>,
      ])}
    />
  );
}
