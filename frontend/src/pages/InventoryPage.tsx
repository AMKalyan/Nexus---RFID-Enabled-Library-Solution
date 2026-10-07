import { useMutation, useQuery } from "@tanstack/react-query";
import { ClipboardCheck, Play, Square } from "lucide-react";
import { useRef, useState } from "react";
import { ApiError } from "../api/client";
import { inventory, type InventoryReadRow, type InventoryReport } from "../api/endpoints";
import { RefusalBanner } from "../components/RefusalBanner";
import { Button, Card, DataTable, PageHeader } from "../components/ui";
import { playConfirmation } from "../lib/audio";
import { useLive } from "../lib/live";

const SHELVES = ["A-01", "A-02", "B-01", "B-02", "C-01", "C-02", "D-01", "D-02"];
const TILE = { green: "border-green-300 bg-green-50 text-green-900", amber: "border-amber-300 bg-amber-50 text-amber-900", red: "border-red-300 bg-red-50 text-red-900" };

/** Shelf inventory with the handheld (AC 05): live green/amber/red confirmations with matching tones. */
export function InventoryPage() {
  const [shelf, setShelf] = useState("A-01");
  const [device, setDevice] = useState("HH-01");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [report, setReport] = useState<InventoryReport | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [sound, setSound] = useState(true);
  const seen = useRef(new Set<string>());

  const live = useQuery({
    queryKey: ["inventory", sessionId],
    queryFn: () => inventory.get(sessionId!),
    enabled: !!sessionId && !report,
    refetchInterval: 3000,
  });

  useLive(["inventory.read"], (m) => {
    const read = m.data as InventoryReadRow & { session_id: string };
    if (read.session_id !== sessionId || seen.current.has(read.epc)) return;
    seen.current.add(read.epc);
    if (sound) playConfirmation(read.beep);
    void live.refetch();
  });

  const start = useMutation({
    mutationFn: () => inventory.start(shelf, device),
    onSuccess: (s) => {
      seen.current = new Set();
      setReport(null);
      setError(null);
      setSessionId(s.id);
    },
    onError: (e) => setError(e as ApiError),
  });
  const close = useMutation({
    mutationFn: () => inventory.close(sessionId!),
    onSuccess: (r) => {
      setReport(r);
      if (sound && r.missing.length) playConfirmation("error");
    },
    onError: (e) => setError(e as ApiError),
  });
  const markMissing = useMutation({ mutationFn: () => inventory.markMissing(sessionId!) });

  const reads = live.data?.reads ?? [];
  return (
    <div>
      <PageHeader title="Inventory">
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={sound} onChange={(e) => setSound(e.target.checked)} /> Sound
        </label>
      </PageHeader>
      {error && <div className="mb-3"><RefusalBanner code={error.code} message={error.message} /></div>}
      <Card className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm text-slate-700">
            Shelf
            <select className="mt-1 block rounded-md border border-slate-300 px-3 py-2 text-sm" value={shelf} onChange={(e) => setShelf(e.target.value)}>
              {SHELVES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="text-sm text-slate-700">
            Handheld
            <input className="mt-1 block w-28 rounded-md border border-slate-300 px-3 py-2 text-sm" value={device} onChange={(e) => setDevice(e.target.value)} />
          </label>
          <Button onClick={() => start.mutate()} disabled={start.isPending}>
            <Play size={14} aria-hidden /> Start session
          </Button>
          <Button variant="secondary" onClick={() => close.mutate()} disabled={!sessionId || !!report}>
            <Square size={14} aria-hidden /> Close and report
          </Button>
          {sessionId && <span className="text-xs text-slate-500">Session <span className="font-mono">{sessionId}</span></span>}
        </div>
      </Card>

      {sessionId && !report && (
        <Card title={`Live reads · ${reads.length} of ${live.data?.expected ?? "?"} expected`}>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {reads.map((r) => (
              <div key={r.epc} className={`rounded-md border p-2 text-xs ${TILE[r.light]}`}>
                <div className="font-medium">{r.title ?? "Unknown tag"}</div>
                <div>
                  {r.accession_no ?? r.epc} · {r.result}
                  {r.result === "misplaced" && ` (belongs on ${r.home_shelf})`}
                </div>
              </div>
            ))}
            {reads.length === 0 && <p className="text-sm text-slate-500">Waiting for the handheld sweep…</p>}
          </div>
        </Card>
      )}

      {report && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Summary label="Found" value={report.found.length} tone="green" />
            <Summary label="Misplaced" value={report.misplaced.length} tone="amber" />
            <Summary label="Missing" value={report.missing.length} tone="red" />
            <Summary label="Unknown tags" value={report.unknown.length} tone="red" />
          </div>
          <Card title="Missing from shelf">
            <DataTable columns={["accession", "title", "epc"]} empty="Nothing missing" rows={report.missing.map((m) => [m.accession_no, m.title, <span className="font-mono text-xs">{m.epc}</span>])} />
            {report.missing.length > 0 && (
              <Button variant="danger" className="mt-3" onClick={() => markMissing.mutate()} disabled={markMissing.isSuccess}>
                <ClipboardCheck size={14} aria-hidden /> {markMissing.isSuccess ? `Marked ${markMissing.data.marked} item(s) missing` : "Confirm and mark missing"}
              </Button>
            )}
          </Card>
          <Card title="Misplaced (found on this shelf, belong elsewhere)">
            <DataTable columns={["accession", "title", "home shelf"]} empty="Nothing misplaced" rows={report.misplaced.map((m) => [m.accession_no, m.title, m.home_shelf])} />
          </Card>
        </div>
      )}
    </div>
  );
}

function Summary({ label, value, tone }: { label: string; value: number; tone: "green" | "amber" | "red" }) {
  return (
    <div className={`rounded-lg border p-4 ${TILE[tone]}`}>
      <div className="text-xs font-medium uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  );
}
