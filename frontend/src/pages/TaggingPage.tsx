import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Radio, ShieldCheck, Tag as TagIcon } from "lucide-react";
import { useState } from "react";
import { ApiError } from "../api/client";
import { catalog, fmtDate, tags, type Item } from "../api/endpoints";
import { RefusalBanner } from "../components/RefusalBanner";
import { Button, Card, DataTable, PageHeader, StatusBadge } from "../components/ui";
import { useLive } from "../lib/live";

type Read = { epc: string; unknown?: boolean; accession_no?: string; title?: string };

/** Tag or re-tag an item (AC 02): find, validate, read a blank tag on the staff station, associate. */
export function TaggingPage() {
  const qc = useQueryClient();
  const [ref, setRef] = useState("");
  const [itemId, setItemId] = useState<string | null>(null);
  const [epc, setEpc] = useState("");
  const [lastRead, setLastRead] = useState<Read | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const item = useQuery({ queryKey: ["item", itemId], queryFn: () => catalog.item(itemId!), enabled: !!itemId });
  const validation = useQuery({ queryKey: ["validate", itemId], queryFn: () => catalog.validate(itemId!), enabled: !!itemId });

  useLive(["tag.read"], (m) => {
    const reads = (m.data as { reads: Read[] }).reads;
    if (reads.length) {
      setLastRead(reads[0]);
      if (reads[0].unknown) setEpc(reads[0].epc);
    }
  });

  async function find() {
    setError(null);
    setNotice(null);
    const value = ref.trim();
    const byAccession = await catalog.findItems({ accession_no: value });
    const found: Item[] = byAccession.length ? byAccession : await catalog.findItems({ barcode: value });
    if (!found.length) {
      setItemId(null);
      setError(new ApiError("ITEM_NOT_FOUND", "No item with that accession number or barcode", 404));
      return;
    }
    setItemId(found[0].id);
  }

  const associate = useMutation({
    mutationFn: () => tags.associate({ epc: epc.trim().toUpperCase(), target_type: "item", item_id: itemId! }),
    onSuccess: (t) => {
      setError(null);
      setNotice(`Tag ${t.epc} is now linked to ${t.item?.accession_no}. Security bit ${t.security_bit ? "on" : "off"}.`);
      setEpc("");
      void qc.invalidateQueries({ queryKey: ["item", itemId] });
    },
    onError: (e) => setError(e as ApiError),
  });

  const i = item.data;
  const problems = validation.data?.problems ?? [];
  return (
    <div>
      <PageHeader title="Tagging" />
      {error && <div className="mb-3"><RefusalBanner code={error.code} message={error.message} /></div>}
      {notice && <p className="mb-3 rounded-md bg-green-50 p-3 text-sm text-green-800">{notice}</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="1. Find the item">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void find();
            }}
          >
            <input className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm" placeholder="Accession number or barcode" value={ref} onChange={(e) => setRef(e.target.value)} />
            <Button type="submit">Find</Button>
          </form>
          {i && (
            <div className="mt-4 space-y-2 text-sm">
              <div className="text-base font-medium">{i.bib.title}</div>
              <div className="text-slate-500">
                {i.accession_no} · {i.call_no ?? "no call no."} · shelf {i.shelf_code ?? "—"} · <StatusBadge status={i.status} />
              </div>
              <div className={`flex items-center gap-2 ${problems.length ? "text-amber-700" : "text-green-700"}`}>
                <ShieldCheck size={16} aria-hidden />
                {problems.length ? `Validation: ${problems.join(", ")}` : "Validated: ready for tagging"}
              </div>
            </div>
          )}
        </Card>
        <Card title="2. Read and associate a tag">
          <div className="mb-3 flex items-center gap-2 rounded-md bg-slate-50 p-3 text-sm text-slate-600">
            <Radio size={16} aria-hidden />
            {lastRead
              ? lastRead.unknown
                ? `Blank tag read on the staff station: ${lastRead.epc}`
                : `Tag ${lastRead.epc} already belongs to ${lastRead.accession_no}`
              : "Place a tag on the staff-station reader, or type its EPC."}
          </div>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              associate.mutate();
            }}
          >
            <input className="flex-1 rounded-md border border-slate-300 px-3 py-2 font-mono text-sm" placeholder="EPC (hex)" value={epc} onChange={(e) => setEpc(e.target.value)} />
            <Button type="submit" disabled={!itemId || !epc || associate.isPending}>
              <TagIcon size={14} aria-hidden /> {i?.active_tag ? "Re-tag" : "Associate"}
            </Button>
          </form>
        </Card>
      </div>
      {i && (
        <Card title="Tag-to-item relationship" className="mt-4">
          <DataTable
            columns={["epc", "status", "security bit", "encoded", "retired", "reason"]}
            empty="This item has never been tagged"
            rows={i.tag_history.map((t) => [
              <span className="font-mono text-xs">{t.epc}</span>,
              <StatusBadge status={t.status} />,
              t.security_bit ? "on" : "off",
              fmtDate(t.encoded_at),
              fmtDate(t.retired_at),
              (t as { retire_reason?: string | null }).retire_reason ?? "—",
            ])}
          />
        </Card>
      )}
    </div>
  );
}
