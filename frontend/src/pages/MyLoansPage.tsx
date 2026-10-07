import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError } from "../api/client";
import { circulation, fmtDay, members } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { RefusalBanner } from "../components/RefusalBanner";
import { Button, Card, DataTable, PageHeader, StatusBadge } from "../components/ui";

export function MyLoansPage() {
  const { user } = useAuth();
  const id = user?.id ?? "";
  const qc = useQueryClient();
  const [refusal, setRefusal] = useState<ApiError | null>(null);
  const loans = useQuery({ queryKey: ["my-loans", id], queryFn: () => members.loans(id), enabled: !!id });
  const fines = useQuery({ queryKey: ["my-fines", id], queryFn: () => members.fines(id), enabled: !!id });
  const renew = useMutation({
    mutationFn: (loanId: string) => circulation.renew({ loan_id: loanId }),
    onSuccess: () => {
      setRefusal(null);
      void qc.invalidateQueries({ queryKey: ["my-loans", id] });
    },
    onError: (e) => setRefusal(e instanceof ApiError ? e : null),
  });

  return (
    <div>
      <PageHeader title="My loans" />
      {refusal && <div className="mb-3"><RefusalBanner code={refusal.code} message={refusal.message} /></div>}
      <DataTable
        columns={["title", "accession", "due", "renewals", ""]}
        empty="You have no items on loan"
        rows={(loans.data ?? []).map((l) => [
          l.title,
          l.accession_no,
          <span className={new Date(l.due_at) < new Date() ? "font-medium text-red-600" : ""}>{fmtDay(l.due_at)}</span>,
          l.renew_count,
          <Button variant="secondary" onClick={() => renew.mutate(l.id)} disabled={renew.isPending}>
            Renew
          </Button>,
        ])}
      />
      <Card title="Fines" className="mt-6">
        <DataTable
          columns={["date", "amount", "reason", "status"]}
          empty="No fines"
          rows={(fines.data ?? []).map((f) => [fmtDay(f.created_at), f.amount, f.reason, <StatusBadge status={f.status} />])}
        />
      </Card>
    </div>
  );
}
