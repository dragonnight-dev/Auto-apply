import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { socketUrl, useServerState } from "./useServerState.js";

class FakeSocket {
  static OPEN = 1;
  static all = [];

  constructor(url) {
    this.url = url;
    this.readyState = FakeSocket.OPEN;
    this.sent = [];
    FakeSocket.all.push(this);
  }

  send(data) {
    this.sent.push(JSON.parse(data));
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
  }

  server(message) {
    act(() => this.onmessage({ data: JSON.stringify(message) }));
  }
}

beforeEach(() => {
  FakeSocket.all = [];
  vi.useFakeTimers();
});
afterEach(() => vi.useRealTimers());

const start = (options = {}) =>
  renderHook(() => useServerState("tok", { WebSocketImpl: FakeSocket, ...options }));

it("builds the socket URL from the page address", () => {
  expect(socketUrl({ protocol: "http:", host: "10.0.0.1:8080" })).toBe("ws://10.0.0.1:8080/ws/boss/");
  expect(socketUrl({ protocol: "https:", host: "x" })).toBe("wss://x/ws/boss/");
});

it("authenticates and applies state snapshots", () => {
  const { result } = start();
  const socket = FakeSocket.all[0];
  act(() => socket.onopen());
  expect(socket.sent).toEqual([{ type: "auth", token: "tok" }]);

  socket.server({ type: "auth_ok" });
  expect(result.current.online).toBe(true);

  socket.server({ type: "state", clients: [{ id: 1 }], session: { id: 2 } });
  expect(result.current.clients).toEqual([{ id: 1 }]);
  expect(result.current.session).toEqual({ id: 2 });
});

it("shows server errors and clears them on the next command", () => {
  const { result } = start();
  FakeSocket.all[0].server({ type: "error", message: "No enabled client is connected." });
  expect(result.current.notice).toBe("No enabled client is connected.");
  act(() => result.current.send({ type: "refresh" }));
  expect(result.current.notice).toBe("");
});

it("reconnects after the socket closes", () => {
  const { result } = start();
  FakeSocket.all[0].server({ type: "auth_ok" });
  act(() => FakeSocket.all[0].close());
  expect(result.current.online).toBe(false);
  act(() => vi.advanceTimersByTime(2000));
  expect(FakeSocket.all).toHaveLength(2);
});

it("a rejected token signs out and stops reconnecting", () => {
  const onAuthFailed = vi.fn();
  start({ onAuthFailed });
  FakeSocket.all[0].server({ type: "auth_failed" });
  act(() => FakeSocket.all[0].close());
  act(() => vi.advanceTimersByTime(10000));
  expect(onAuthFailed).toHaveBeenCalledOnce();
  expect(FakeSocket.all).toHaveLength(1);
});

it("unmounting closes the socket without reconnecting", () => {
  const { unmount } = start();
  unmount();
  act(() => vi.advanceTimersByTime(10000));
  expect(FakeSocket.all).toHaveLength(1);
  expect(FakeSocket.all[0].readyState).toBe(3);
});

it("explains when a command cannot be sent", () => {
  const { result } = start();
  act(() => FakeSocket.all[0].close());
  act(() => result.current.send({ type: "sync" }));
  expect(result.current.notice).toMatch(/Not connected/);
});
