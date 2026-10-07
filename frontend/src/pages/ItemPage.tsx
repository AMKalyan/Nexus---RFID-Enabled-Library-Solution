import { useMutation, useQuery } from "@tanstack/react-query";
import { Printer, ShieldCheck } from "lucide-react";
import { useParams } from "react-router-dom";
import { catalog, download, fmtDate } from "../api/endpoints";
import { Button, Card, DataTable, ErrorText, PageHeader, StatusBadge } from "../components/ui";

export function ItemPage() {
  const { id = "" } = useParams();
  const item = useQuery({ queryKey: ["item", id], queryFn: () => catalog.item(id) });
  const validate = useMutation({ mutationFn: () => catalog.validate(id) });
  const i = item.data;

  return (
    <div>
      <PageHeader title={i ? i.bib.title : "Item"}>
        <Button variant="secondary" onClick={() => validate.mutate()}>
          <ShieldCheck size={14} aria-hidden /> Validate for tagging
        </Button>
        <Button variant="secondary" onClick={() => void download(`/items/${id}/spine-label.pdf`, `spine-${i?.accession_no}.pdf`)}>
          <Printer size={14} aria-hidden /> Spine label
        </Button>
      </PageHeader>
      <ErrorText error={item.error} />
      {validate.data && (
        <p className={`mb-3 text-sm ${validate.data.problems.length ? "text-red-600" : "text-green-700"}`}>
          {validate.data.problems.length ? `Cannot tag: ${validate.data.problems.join(", ")}` : "Item is valid for tagging"}
        </p>
      )}
      {i && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Item">
            <dl className="grid grid-cols-[140px_1fr] gap-y-2 text-sm">
              <dt className="text-slate-500">Accession no.</dt>
              <dd>{i.accession_no}</dd>
              <dt className="text-slate-500">Barcode</dt>
              <dd>{i.barcode}</dd>
              <dt className="text-slate-500">Call no.</dt>
              <dd>{i.call_no ?? "—"}</dd>
              <dt className="text-slate-500">Shelf</dt>
              <dd>{i.shelf_code ?? "—"}</dd>
              <dt className="text-slate-500">Type</dt>
              <dd>{i.item_type}</dd>
              <dt className="text-slate-500">Status</dt>
              <dd>
                <StatusBadge status={i.status} />
              </dd>
              <dt className="text-slate-500">Author</dt>
              <dd>{i.bib.author ?? "—"}</dd>
            </dl>
          </Card>
          <Card title="RFID tag">
            {i.active_tag ? (
              <div className="mb-3 rounded-md border border-green-200 bg-green-50 p-3 text-sm">
                <div className="font-mono text-green-900">{i.active_tag.epc}</div>
                <div className="text-green-700">
                  Security bit {i.active_tag.security_bit ? "ON (gate alarms)" : "OFF (on loan)"} · encoded {fmtDate(i.active_tag.encoded_at)}
                </div>
              </div>
            ) : (
              <p className="mb-3 text-sm text-slate-500">No active tag.</p>
            )}
            <DataTable
              columns={["epc", "status", "encoded", "retired"]}
              empty="No tag history"
              rows={i.tag_history.map((t) => [<span className="font-mono text-xs">{t.epc}</span>, <StatusBadge status={t.status} />, fmtDate(t.encoded_at), fmtDate(t.retired_at)])}
            />
          </Card>
        </div>
      )}
    </div>
  );
}
