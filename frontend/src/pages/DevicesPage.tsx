import { useQuery } from "@tanstack/react-query";
import { devices, fmtDate, notifications } from "../api/endpoints";
import { RequirePermission } from "../auth/AuthContext";
import { Card, DataTable, PageHeader, StatusBadge } from "../components/ui";

export function DevicesPage() {
  const list = useQuery({ queryKey: ["devices"], queryFn: devices.list, refetchInterval: 10_000 });
  return (
    <div>
      <PageHeader title="Devices" />
      <DataTable
        columns={["code", "type", "name", "location", "ip address", "status", "last heartbeat"]}
        rows={(list.data ?? []).map((d) => [
          <span className="font-mono">{d.code}</span>,
          d.device_type.replace("_", " "),
          d.name,
          d.location ?? "—",
          d.ip_address ?? "—",
          <StatusBadge status={d.status === "online" ? "active" : "missing"} />,
          fmtDate(d.last_heartbeat_at),
        ])}
      />
      <p className="mt-2 text-xs text-slate-500">A device is offline when no event has arrived for 30 seconds.</p>
      <RequirePermission perm="notifications.read">
        <Outbox />
      </RequirePermission>
    </div>
  );
}

function Outbox() {
  const rows = useQuery({ queryKey: ["outbox"], queryFn: () => notifications.outbox(), refetchInterval: 10_000 });
  return (
    <Card title="Notification outbox" className="mt-6">
      <DataTable
        columns={["created", "channel", "recipient", "subject", "status", "attempts", "last error"]}
        empty="No notifications"
        rows={(rows.data ?? []).map((r) => [
          fmtDate(r.created_at),
          r.channel,
          r.recipient,
          r.subject ?? r.template,
          <StatusBadge status={r.status === "sent" ? "paid" : r.status === "failed" ? "blocked" : "open"} />,
          r.attempts,
          r.last_error ?? "—",
        ])}
      />
    </Card>
  );
}
