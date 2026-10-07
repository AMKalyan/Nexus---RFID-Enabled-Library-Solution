import { api, getTokens } from "./client";

export type Bib = {
  id: string;
  title: string;
  author: string | null;
  isbn: string | null;
  publisher: string | null;
  pub_year: number | null;
  edition: string | null;
  subjects: string | null;
  source: string;
};
export type Tag = { epc: string; status: string; security_bit: boolean; encoded_at: string; retired_at: string | null };
export type Item = {
  id: string;
  bib_id: string;
  accession_no: string;
  barcode: string;
  call_no: string | null;
  shelf_code: string | null;
  item_type: "lending" | "reference";
  status: string;
  bib: { id: string; title: string; author: string | null; pub_year: number | null };
  active_tag: Tag | null;
  tag_history: Tag[];
};
export type OpacHit = {
  id: string;
  title: string;
  author: string | null;
  publisher: string | null;
  pub_year: number | null;
  isbn: string | null;
  total_copies: number;
  available_copies: number;
};
export type OpacPage = { total: number; page: number; size: number; items: OpacHit[] };
export type Spine = { item_id: string; accession_no: string; call_no: string | null; title: string; author: string | null; status: string };
export type Member = {
  id: string;
  card_no: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  category_code: string;
  status: "active" | "blocked" | "expired";
  block_reason: string | null;
};
export type MemberSummary = Member & { open_fines: string; fine_limit: string; open_loans: number; max_items: number };
export type Loan = {
  id: string;
  item_id: string;
  member_id: string;
  issued_at: string;
  due_at: string;
  returned_at: string | null;
  renew_count: number;
  channel: string;
};
export type LoanDetail = Loan & { accession_no: string; title: string };
export type Fine = { id: string; amount: string; reason: string; status: string; created_at: string };
export type Checkin = { loan: Loan; fine: Fine | null };
export type Dashboard = {
  tagged_items: number;
  untagged_items: number;
  members_active: number;
  members_blocked: number;
  loans_active: number;
  loans_overdue: number;
  fines_open_total: string;
  gate_alarms_today: number;
  footfall_today: { in: number; out: number };
  loans_by_day: { date: string; count: number }[];
  top_titles: { title: string; loans: number }[];
};
export type Report = { name: string; title: string; columns: string[]; rows: unknown[][]; filters: string[] };
export type StaffUser = {
  id: string;
  username: string;
  display_name: string;
  email: string | null;
  role: string;
  is_active: boolean;
  has_smartcard: boolean;
  last_login_at: string | null;
};
export type Policy = {
  category_code: string;
  name: string;
  loan_days: number;
  max_items: number;
  max_renewals: number;
  fine_per_day: string;
  fine_limit: string;
  can_borrow_reference: boolean;
};
export type AuditEntry = {
  id: number;
  occurred_at: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  details: Record<string, unknown>;
  ip: string | null;
};

const post = <T,>(path: string, body?: unknown) => api<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) });
const patch = <T,>(path: string, body: unknown) => api<T>(path, { method: "PATCH", body: JSON.stringify(body) });
const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const opac = {
  search: (params: { q?: string; author?: string; year_from?: number; year_to?: number; available?: boolean; page?: number }) =>
    api<OpacPage>(`/opac/search${qs(params)}`),
  shelf: (code: string) => api<Spine[]>(`/opac/shelves/${encodeURIComponent(code)}`),
};

export const catalog = {
  bibs: (q: string) => api<Bib[]>(`/bibs${qs({ q })}`),
  createBib: (body: Partial<Bib>) => post<Bib>("/bibs", body),
  addItem: (bibId: string, body: Record<string, unknown>) => post<Item>(`/bibs/${bibId}/items`, body),
  findItems: (params: { accession_no?: string; barcode?: string; epc?: string }) => api<Item[]>(`/items${qs(params)}`),
  item: (id: string) => api<Item>(`/items/${id}`),
  validate: (id: string) => post<{ problems: string[] }>(`/items/${id}/validate`),
};

export const members = {
  search: (q: string) => api<Member[]>(`/members${qs({ q })}`),
  get: (id: string) => api<MemberSummary>(`/members/${id}`),
  create: (body: Record<string, unknown>) => post<Member>("/members", body),
  block: (id: string, reason: string) => post<Member>(`/members/${id}/block`, { reason }),
  unblock: (id: string) => post<Member>(`/members/${id}/unblock`),
  loans: (id: string, history = false) => api<LoanDetail[]>(`/members/${id}/loans${qs({ history })}`),
  fines: (id: string) => api<Fine[]>(`/members/${id}/fines`),
};

export const circulation = {
  checkout: (member_card_no: string, item: string) => post<Loan>("/circulation/checkout", { member_card_no, item }),
  renew: (body: { item?: string; loan_id?: string }) => post<Loan>("/circulation/renew", body),
  checkin: (item: string) => post<Checkin>("/circulation/checkin", { item }),
};

export const fines = {
  pay: (id: string) => post<Fine>(`/fines/${id}/pay`),
  waive: (id: string, reason: string) => post<Fine>(`/fines/${id}/waive`, { reason }),
};

export const reports = {
  dashboard: () => api<Dashboard>("/reports/dashboard"),
  run: (name: string, params: Record<string, string>) => api<Report>(`/reports/${name}${qs(params)}`),
};

export const admin = {
  users: () => api<StaffUser[]>("/admin/users"),
  createUser: (body: Record<string, unknown>) => post<StaffUser>("/admin/users", body),
  updateUser: (id: string, body: Record<string, unknown>) => patch<StaffUser>(`/admin/users/${id}`, body),
  policies: () => api<Policy[]>("/admin/policies"),
  updatePolicy: (code: string, body: Record<string, unknown>) => patch<Policy>(`/admin/policies/${code}`, body),
  audit: (params: Record<string, string | number>) =>
    api<{ total: number; items: AuditEntry[] }>(`/admin/audit${qs(params)}`),
};

/** Download a file from an authenticated endpoint without exposing the token in a URL. */
export async function download(path: string, filename: string): Promise<void> {
  const res = await fetch(`/api/v1${path}`, {
    headers: getTokens() ? { Authorization: `Bearer ${getTokens()!.access_token}` } : {},
  });
  if (!res.ok) throw new Error("Download failed");
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const fmtDate = (iso: string | null) => (iso ? new Date(iso).toLocaleString() : "—");
export const fmtDay = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString() : "—");
