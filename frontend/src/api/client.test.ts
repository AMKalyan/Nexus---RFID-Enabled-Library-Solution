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
