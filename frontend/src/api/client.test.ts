import { describe, it, expect, vi, beforeEach } from "vitest";
import { api, setTokens, ApiError } from "./client";

describe("api client", () => {
  beforeEach(() => setTokens({ access_token: "old", refresh_token: "r1" }));

  it("refreshes once on 401 and retries", async () => {
    const f = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: "x", code: "ERR_TOKEN_INVALID" }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: "new", refresh_token: "r2" }), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } }),
      );
    vi.stubGlobal("fetch", f);
    expect(await api<{ ok: boolean }>("/x")).toEqual({ ok: true });
    expect(f.mock.calls[2][1].headers.Authorization).toBe("Bearer new");
  });

  it("throws ApiError with server code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: "Member is blocked", code: "MEMBER_BLOCKED" }), { status: 409 }),
      ),
    );
    await expect(api("/y")).rejects.toMatchObject({ code: "MEMBER_BLOCKED", status: 409 } as Partial<ApiError>);
  });
});

describe("health", () => {
  it("returns the degraded report that comes with a 503 (DEF-024)", async () => {
    const { getHealth } = await import("./client");
    const body = { status: "degraded", checks: { database: false } };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 503, headers: { "content-type": "application/json" } })),
    );
    expect(await getHealth()).toEqual(body);
  });

  it("still throws for answers that are not a health report", async () => {
    const { getHealth } = await import("./client");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("bad gateway", { status: 502 })));
    await expect(getHealth()).rejects.toMatchObject({ status: 502 } as Partial<ApiError>);
  });
});
