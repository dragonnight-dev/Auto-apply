import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "./App.jsx";

class FakeSocket {
  static OPEN = 1;
  static latest = null;

  constructor() {
    this.readyState = FakeSocket.OPEN;
    this.sent = [];
    FakeSocket.latest = this;
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

const STATE = {
  type: "state",
  clients: [{ id: 1, email: "ann@example.com", name: "Ann", enabled: true, connected: true,
    url: "https://jobs.example/1", action: "no-action" }],
  session: { id: 7, url: "https://jobs.example/1", state: "ready", error: "", title: "Engineer", plans: [] },
};

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn(async (url) => new Response(JSON.stringify(
    url === "/api/stats" ? { clients: [] } : { token: "new-token", enabled: false },
  ), { status: 200 })));
});
afterEach(() => vi.unstubAllGlobals());

async function signedIn() {
  localStorage.setItem("auto-apply-token", "tok");
  render(<App WebSocketImpl={FakeSocket} />);
  const socket = FakeSocket.latest;
  act(() => socket.onopen());
  socket.server({ type: "auth_ok" });
  socket.server(STATE);
  socket.sent.length = 0;
  await act(async () => {});
  return socket;
}

it("shows sign-in without a token and keeps the token after signing in", async () => {
  render(<App WebSocketImpl={FakeSocket} />);
  await userEvent.type(screen.getByLabelText("Username"), "boss");
  await userEvent.type(screen.getByLabelText("Password"), "long-enough");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("heading", { name: "Clients" })).toBeInTheDocument();
  expect(localStorage.getItem("auto-apply-token")).toBe("new-token");
});

it("sync and fill reach the server over the socket", async () => {
  const socket = await signedIn();
  await userEvent.click(screen.getByRole("button", { name: /Sync all clients/ }));
  expect(socket.sent.at(-1)).toEqual({ type: "sync", url: "https://jobs.example/1" });
  await userEvent.click(screen.getByRole("button", { name: "Fill data" }));
  expect(socket.sent.at(-1)).toEqual({ type: "fill", session_id: 7 });
});

it("toggling a client calls the API with the token", async () => {
  await signedIn();
  await userEvent.click(screen.getByRole("checkbox", { name: "Enable ann@example.com" }));
  const call = fetch.mock.calls.find(([url]) => url === "/api/clients/1");
  expect(call[1].headers.Authorization).toBe("Bearer tok");
});

it("shows a server error notice", async () => {
  const socket = await signedIn();
  socket.server({ type: "error", message: "No enabled client is connected." });
  expect(screen.getByRole("alert")).toHaveTextContent("No enabled client is connected.");
});

it("signing out clears the token", async () => {
  await signedIn();
  await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(localStorage.getItem("auto-apply-token")).toBeNull();
  expect(screen.getByLabelText("Username")).toBeInTheDocument();
});

it("a rejected token returns to sign-in", async () => {
  const socket = await signedIn();
  socket.server({ type: "auth_failed" });
  expect(screen.getByLabelText("Username")).toBeInTheDocument();
  expect(localStorage.getItem("auto-apply-token")).toBeNull();
});
