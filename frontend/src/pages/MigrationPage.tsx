import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileSpreadsheet, RotateCcw, Upload } from "lucide-react";
import { useState } from "react";
import { api, ApiError, getTokens } from "../api/client";
import { download, fmtDate } from "../api/endpoints";
import { RefusalBanner } from "../components/RefusalBanner";
import { Button, Card, DataTable, PageHeader, StatTile, StatusBadge } from "../components/ui";

type Batch = { id: string; source_file: string; status: string; rows_total: number; rows_committed: number; created_at: string };
type Report = {
  batch_id: string;
  status: string;
  source: number;
  valid: number;
  rejected: number;
  duplicate: number;
  likely_duplicate: number;
  committed: number;
  balanced: boolean;
  by_reason: Record<string, number>;
  backup_file: string | null;
};

async function uploadFile(file: File): Promise<Batch> {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch("/api/v1/migration/batches", {
    method: "POST",
    body,
    headers: getTokens() ? { Authorization: `Bearer ${getTokens()!.access_token}` } : {},
  });
  const json = await res.json();
  if (!res.ok) throw new ApiError(json.code ?? "ERR_UNKNOWN", json.error ?? "Upload failed", res.status);
  return json as Batch;
}

/** Migration console (AC 01): upload, dry run, reconcile, commit with backup, roll back. */
export function MigrationPage() {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const batches = useQuery({ queryKey: ["batches"], queryFn: () => api<Batch[]>("/migration/batches") });
  const refresh = () => void qc.invalidateQueries({ queryKey: ["batches"] });
  const onError = (e: unknown) => setError(e as ApiError);

  const stage = useMutation({
    mutationFn: () => uploadFile(file!),
    onSuccess: (b) => {
      setError(null);
      setBatch(b);
      setReport(null);
      refresh();
    },
    onError,
  });
  const run = useMutation({
    mutationFn: (action: "validate" | "commit" | "rollback") =>
      api<Report>(`/migration/batches/${batch!.id}/${action}`, { method: "POST" }),
    onSuccess: (r) => {
      setError(null);
      setReport(r);
      refresh();
    },
    onError,
  });

  const commit = () => {
    if (window.confirm(`Commit ${report?.valid.toLocaleString()} rows? A full database backup is taken first.`)) run.mutate("commit");
  };

  return (
    <div>
      <PageHeader title="Data migration" />
      {error && <div className="mb-3"><RefusalBanner code={error.code} message={error.message} /></div>}
      <Card className="mb-4" title="1. Upload a spreadsheet (.xlsx or .csv)">
        <div className="flex flex-wrap items-center gap-3">
          <input type="file" accept=".xlsx,.csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm" />
          <Button disabled={!file || stage.isPending} onClick={() => stage.mutate()}>
            <Upload size={14} aria-hidden /> {stage.isPending ? "Staging…" : "Stage"}
          </Button>
          {batch && (
            <span className="text-sm text-slate-600">
              <FileSpreadsheet size={14} className="mr-1 inline" aria-hidden />
              {batch.source_file}: {batch.rows_total.toLocaleString()} rows staged
            </span>
          )}
        </div>
      </Card>

      {batch && (
        <Card className="mb-4" title="2. Validate, reconcile and commit">
          <div className="mb-4 flex flex-wrap gap-2">
            <Button variant="secondary" disabled={run.isPending} onClick={() => run.mutate("validate")}>
              Validate (dry run)
            </Button>
            <Button disabled={run.isPending || report?.status !== "validated"} onClick={commit}>
              <CheckCircle2 size={14} aria-hidden /> Commit
            </Button>
            <Button variant="danger" disabled={run.isPending || report?.status !== "committed"} onClick={() => run.mutate("rollback")}>
              <RotateCcw size={14} aria-hidden /> Roll back batch
            </Button>
            {report && (
              <Button variant="secondary" onClick={() => void download(`/migration/batches/${batch.id}/report?format=csv`, `migration-${batch.id}.csv`)}>
                Row-level report (CSV)
              </Button>
            )}
          </div>
          {report && (
            <>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
                <StatTile label="Source rows" value={report.source.toLocaleString()} />
                <StatTile label="Valid" value={report.valid.toLocaleString()} />
                <StatTile label="Rejected" value={report.rejected.toLocaleString()} tone={report.rejected ? "warn" : "default"} />
                <StatTile label="Duplicates" value={report.duplicate.toLocaleString()} tone={report.duplicate ? "warn" : "default"} />
                <StatTile label="Likely duplicates" value={report.likely_duplicate.toLocaleString()} />
                <StatTile label="Committed" value={report.committed.toLocaleString()} />
              </div>
              <p className={`mt-3 text-sm font-medium ${report.balanced ? "text-green-700" : "text-red-700"}`}>
                Reconciliation {report.balanced ? "balanced" : "NOT balanced"}: {report.source.toLocaleString()} = {report.valid.toLocaleString()} valid +{" "}
                {report.rejected.toLocaleString()} rejected + {report.duplicate.toLocaleString()} duplicate
                {report.status === "committed" && `; ${report.committed.toLocaleString()} committed`}
              </p>
              {report.backup_file && <p className="text-xs text-slate-500">Backup taken before commit: {report.backup_file}</p>}
              {Object.keys(report.by_reason).length > 0 && (
                <div className="mt-3">
                  <DataTable columns={["reason", "rows"]} rows={Object.entries(report.by_reason).map(([k, v]) => [k, v])} />
                </div>
              )}
            </>
          )}
        </Card>
      )}

      <Card title="Recent batches">
        <DataTable
          columns={["created", "file", "rows", "committed", "status"]}
          empty="No migrations yet"
          rows={(batches.data ?? []).map((b) => [fmtDate(b.created_at), b.source_file, b.rows_total.toLocaleString(), b.rows_committed.toLocaleString(), <StatusBadge status={b.status} />])}
        />
      </Card>
    </div>
  );
}
