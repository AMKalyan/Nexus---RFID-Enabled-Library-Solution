import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownToLine, ArrowUpFromLine, RefreshCw } from "lucide-react";
import { useState } from "react";
import { ApiError } from "../api/client";
import { circulation, fmtDay, members, type MemberSummary } from "../api/endpoints";
import { RefusalBanner } from "../components/RefusalBanner";
import { Button, Card, DataTable, PageHeader, StatusBadge } from "../components/ui";

type Notice = { tone: "ok" | "refused"; text?: string; error?: ApiError };

export function CirculationDeskPage() {
  const qc = useQueryClient();
  const [cardNo, setCardNo] = useState("");
  const [member, setMember] = useState<MemberSummary | null>(null);
  const [itemRef, setItemRef] = useState("");
  const [notice, setNotice] = useState<Notice | null>(null);

  const loans = useQuery({
    queryKey: ["desk-loans", member?.id],
    queryFn: () => members.loans(member!.id),
    enabled: !!member,
  });

  async function lookUp() {
    setNotice(null);
    try {
      const found = await members.search(cardNo.trim());
      const exact = found.find((m) => m.card_no === cardNo.trim());
      if (!exact) throw new ApiError("MEMBER_NOT_FOUND", "No member with that card number", 404);
      setMember(await members.get(exact.id));
      // Looking up the same member again must also refresh their loans (made at a kiosk, by NCIP, ...).
      void qc.invalidateQueries({ queryKey: ["desk-loans", exact.id] });
    } catch (e) {
      setMember(null);
      setNotice({ tone: "refused", error: e as ApiError });
    }
  }

  async function refreshMember() {
    if (member) setMember(await members.get(member.id));
    void qc.invalidateQueries({ queryKey: ["desk-loans"] });
  }

  const run = useMutation({
    mutationFn: async (op: "checkout" | "renew" | "checkin") => {
      const ref = itemRef.trim();
      if (op === "checkout") {
        const loan = await circulation.checkout(member!.card_no, ref);
        return `Issued ${ref}, due ${fmtDay(loan.due_at)}`;
      }
      if (op === "renew") {
        const loan = await circulation.renew({ item: ref });
        return `Renewed ${ref}, now due ${fmtDay(loan.due_at)}`;
      }
      const result = await circulation.checkin(ref);
      return result.fine ? `Returned ${ref}. Overdue fine raised: ${result.fine.amount}` : `Returned ${ref}`;
    },
    onSuccess: async (text) => {
      setNotice({ tone: "ok", text });
      setItemRef("");
      await refreshMember();
    },
    onError: (e) => setNotice({ tone: "refused", error: e as ApiError }),
  });

  return (
    <div>
      <PageHeader title="Circulation desk" />
      <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
        <Card title="Member">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void lookUp();
            }}
          >
            <input autoFocus className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="Scan or type card number" value={cardNo} onChange={(e) => setCardNo(e.target.value)} />
            <Button type="submit">Look up</Button>
          </form>
          {member && (
            <div className="mt-4 space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-base font-medium">{member.full_name}</span>
                <StatusBadge status={member.status} />
              </div>
              <div className="text-slate-500">
                {member.card_no} · category {member.category_code}
              </div>
              {member.block_reason && <div className="text-red-600">Blocked: {member.block_reason}</div>}
              <div className="grid grid-cols-2 gap-2 pt-2">
                <div className="rounded bg-slate-50 p-2">
                  Loans <b>{member.open_loans}</b> / {member.max_items}
                </div>
                <div className={`rounded p-2 ${Number(member.open_fines) > Number(member.fine_limit) ? "bg-red-50 text-red-700" : "bg-slate-50"}`}>
                  Fines <b>{member.open_fines}</b> / limit {member.fine_limit}
                </div>
              </div>
            </div>
          )}
        </Card>
        <Card title="Item">
          <input className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="Accession number, barcode or tag EPC" value={itemRef} onChange={(e) => setItemRef(e.target.value)} />
          <div className="mt-3 flex flex-wrap gap-2">
            <Button disabled={!member || !itemRef || run.isPending} onClick={() => run.mutate("checkout")}>
              <ArrowUpFromLine size={14} aria-hidden /> Check out
            </Button>
            <Button variant="secondary" disabled={!itemRef || run.isPending} onClick={() => run.mutate("renew")}>
              <RefreshCw size={14} aria-hidden /> Renew
            </Button>
            <Button variant="secondary" disabled={!itemRef || run.isPending} onClick={() => run.mutate("checkin")}>
              <ArrowDownToLine size={14} aria-hidden /> Check in
            </Button>
          </div>
          <div className="mt-3">
            {notice?.tone === "refused" && notice.error && <RefusalBanner code={notice.error.code} message={notice.error.message} />}
            {notice?.tone === "ok" && <p className="rounded-md bg-green-50 p-3 text-sm text-green-800">{notice.text}</p>}
          </div>
        </Card>
      </div>
      {member && (
        <Card title="Current loans" className="mt-4">
          <DataTable
            columns={["title", "accession", "issued", "due", "renewals", "channel"]}
            empty="No items on loan"
            rows={(loans.data ?? []).map((l) => [
              l.title,
              l.accession_no,
              fmtDay(l.issued_at),
              <span className={new Date(l.due_at) < new Date() ? "font-medium text-red-600" : ""}>{fmtDay(l.due_at)}</span>,
              l.renew_count,
              l.channel,
            ])}
          />
        </Card>
      )}
    </div>
  );
}
