export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export type Tokens = { access_token: string; refresh_token: string };

// Tokens live in memory only; nothing is persisted where injected script could read it later.
let tokens: Tokens | null = null;
export const setTokens = (t: Tokens | null) => {
  tokens = t;
};
export const getTokens = () => tokens;

const BASE = "/api/v1";

async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(init.headers as Record<string, string>) };
  if (tokens) headers.Authorization = `Bearer ${tokens.access_token}`;
  return fetch(BASE + path, { ...init, headers });
}

async function refresh(): Promise<boolean> {
  if (!tokens) return false;
  const r = await fetch(BASE + "/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokens.refresh_token }),
  });
  if (!r.ok) {
    setTokens(null);
    return false;
  }
  setTokens(await r.json());
  return true;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res = await send(path, init);
  if (res.status === 401 && (await refresh())) res = await send(path, init);
  const isJson = res.headers.get("content-type")?.includes("json") || res.status >= 400;
  const body = isJson ? await res.json().catch(() => ({})) : await res.blob();
  if (!res.ok) throw new ApiError(body.code ?? "ERR_UNKNOWN", body.error ?? "Request failed", res.status);
  return body as T;
}
