import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, CameraOff, WifiOff } from "lucide-react";
import { useEffect, useState } from "react";
import { fmtDate, gate, type GateEvent } from "../api/endpoints";
import { Card, PageHeader } from "../components/ui";
import { playConfirmation } from "../lib/audio";
import { useLive } from "../lib/live";

/** Security gate monitor (AC 06): live alarms with the CCTV snapshot and notification status. */
export function GateMonitorPage() {
  const qc = useQueryClient();
  const [alarmsOnly, setAlarmsOnly] = useState(true);
  const [flash, setFlash] = useState(false);
  const events = useQuery({ queryKey: ["gate", alarmsOnly], queryFn: () => gate.events(alarmsOnly), refetchInterval: 15_000 });

  useLive(["gate.alert"], () => {
    playConfirmation("error");
    setFlash(true);
    setTimeout(() => setFlash(false), 2500);
    void qc.invalidateQueries({ queryKey: ["gate"] });
  });

  return (
    <div>
      <PageHeader title="Gate monitor">
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={alarmsOnly} onChange={(e) => setAlarmsOnly(e.target.checked)} /> Alarms only
        </label>
      </PageHeader>
      {flash && (
        <div role="alert" className="mb-4 flex items-center gap-3 rounded-md bg-red-600 p-4 text-white">
          <BellRing aria-hidden /> Security gate alarm
        </div>
      )}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {(events.data ?? []).map((e) => (
          <GateCard key={e.id} event={e} />
        ))}
        {events.data?.length === 0 && <p className="text-sm text-slate-500">No gate events.</p>}
      </div>
    </div>
  );
}

function GateCard({ event }: { event: GateEvent }) {
  const [photo, setPhoto] = useState<string | null>(null);
  useEffect(() => {
    if (!event.has_photo) return;
    let url: string | null = null;
    gate.photoUrl(event.id).then((u) => setPhoto((url = u))).catch(() => setPhoto(null));
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [event.id, event.has_photo]);

  return (
    <Card className={event.alarm ? "border-red-300" : ""}>
      {photo ? (
        <img src={photo} alt={`Camera snapshot at ${event.device_code}`} className="mb-3 w-full rounded" />
      ) : (
        <div className="mb-3 flex h-28 items-center justify-center rounded bg-slate-100 text-slate-400">
          <CameraOff aria-hidden />
        </div>
      )}
      <div className="flex items-center justify-between">
        <span className={`text-sm font-semibold ${event.alarm ? "text-red-700" : "text-green-700"}`}>
          {event.alarm ? "ALARM" : event.authorised ? "Authorised" : "Passage"} · {event.direction}
        </span>
        {event.offline_decision && (
          <span className="flex items-center gap-1 rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
            <WifiOff size={12} aria-hidden /> decided offline
          </span>
        )}
      </div>
      <div className="mt-1 text-sm text-slate-700">Accession: {event.accession_no ?? "unknown tag"}</div>
      <div className="text-xs text-slate-500">
        {event.device_code} · {fmtDate(event.occurred_at)} · {event.notified ? "email queued" : "no notification"}
      </div>
    </Card>
  );
}
