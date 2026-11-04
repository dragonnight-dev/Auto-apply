import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, clearHistory, request, setClientEnabled } from "./api.js";

const reply = (status, body) =>
  vi.fn(async () => new Response(body === undefined ? null : JSON.stringify(body), { status }));

afterEach(() => vi.unstubAllGlobals());

describe("request", () => {
  it("sends JSON with the bearer token", async () => {
    const fetchMock = reply(200, { ok: 1 });
    vi.stubGlobal("fetch", fetchMock);
    await expect(setClientEnabled("tok", 3, false)).resolves.toEqual({ ok: 1 });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/clients/3");
    expect(options.method).toBe("PATCH");
    expect(options.headers.Authorization).toBe("Bearer tok");
    expect(JSON.parse(options.body)).toEqual({ enabled: false });
  });

  it("returns null for an empty 204 reply", async () => {
    vi.stubGlobal("fetch", reply(204));
    await expect(clearHistory("tok", 1)).resolves.toBeNull();
  });

  it("raises the server's message and status", async () => {
    vi.stubGlobal("fetch", reply(403, { error: "Invalid boss key." }));
    const error = await request("x").catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toBe("Invalid boss key.");
    expect(error.status).toBe(403);
  });

  it("explains an unreachable server and a non-JSON error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("network"); }));
    await expect(request("x")).rejects.toThrow("Cannot reach the server.");
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>", { status: 502 })));
    await expect(request("x")).rejects.toThrow("502");
  });
});
