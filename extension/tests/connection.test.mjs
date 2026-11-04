import assert from "node:assert/strict";
import { test } from "node:test";
import { ClientConnection, toWebSocketUrl } from "../src/connection.js";

class FakeSocket {
  static OPEN = 1;
  static instances = [];

  constructor(url) {
    this.url = url;
    this.readyState = FakeSocket.OPEN;
    this.sent = [];
    FakeSocket.instances.push(this);
  }

  send(data) {
    this.sent.push(JSON.parse(data));
  }

  close() {
    this.readyState = 3;
    this.onclose?.();
  }

  server(message) {
    return this.onmessage({ data: JSON.stringify(message) });
  }
}

function fakeTimers() {
  const timers = {
    delays: [],
    pending: [],
    intervals: 0,
    setTimeout(fn, delay) {
      timers.delays.push(delay);
      timers.pending.push(fn);
      return timers.pending.length;
    },
    clearTimeout() {},
    setInterval() {
      timers.intervals += 1;
      return timers.intervals;
    },
    clearInterval() {},
    runNext() {
      timers.pending.shift()();
    },
  };
  return timers;
}

function setup(browserOverrides = {}) {
  FakeSocket.instances = [];
  const statuses = [];
  const timers = fakeTimers();
  const browser = {
    activeUrl: async () => "https://active.example/",
    navigate: async () => {},
    capture: async () => ({ fields: [] }),
    apply: async () => [{ ok: true }],
    ...browserOverrides,
  };
  const connection = new ClientConnection({
    serverUrl: "http://192.168.1.10:8000/",
    token: "tok",
    browser,
    WebSocketImpl: FakeSocket,
    onStatus: (status) => statuses.push(status),
    timers,
  });
  connection.start();
  const socket = FakeSocket.instances[0];
  return { connection, socket, statuses, timers };
}

async function setupConnected(browserOverrides) {
  const context = setup(browserOverrides);
  context.socket.onopen();
  await context.socket.server({ type: "auth_ok" });
  context.socket.sent.length = 0;
  return context;
}

test("converts server URLs to socket URLs", () => {
  assert.equal(toWebSocketUrl("http://10.0.0.1:8000"), "ws://10.0.0.1:8000/ws/client/");
  assert.equal(toWebSocketUrl("https://host/app?x=1"), "wss://host/ws/client/");
  assert.throws(() => toWebSocketUrl("not a url"));
});

test("authenticates first, then reports connected", async () => {
  const { socket, statuses, timers } = setup();
  assert.equal(socket.url, "ws://192.168.1.10:8000/ws/client/");
  socket.onopen();
  assert.deepEqual(socket.sent, [{ type: "auth", token: "tok" }]);
  await socket.server({ type: "auth_ok" });
  assert.equal(statuses.at(-1), "connected");
  assert.equal(timers.intervals, 1);
});

test("reports the active URL on request, and only when authenticated", async () => {
  const { connection, socket } = setup();
  socket.onopen();
  connection.reportUrl("https://early.example/");
  assert.equal(socket.sent.length, 1);
  await socket.server({ type: "auth_ok" });
  await socket.server({ type: "get_url" });
  assert.deepEqual(socket.sent.at(-1), { type: "url", url: "https://active.example/" });
});

test("reconnects with growing, capped backoff and resets it on success", async () => {
  const { socket, timers } = setup();
  socket.close();
  assert.deepEqual(timers.delays, [1000]);
  timers.runNext();
  FakeSocket.instances[1].close();
  assert.deepEqual(timers.delays, [1000, 2000]);
  for (let i = 0; i < 8; i += 1) {
    timers.runNext();
    FakeSocket.instances.at(-1).close();
  }
  assert.equal(timers.delays.at(-1), 30000);
  timers.runNext();
  const latest = FakeSocket.instances.at(-1);
  latest.onopen();
  await latest.server({ type: "auth_ok" });
  latest.close();
  assert.equal(timers.delays.at(-1), 1000);
});

test("a rejected token stops reconnecting", async () => {
  const { socket, statuses, timers } = setup();
  socket.onopen();
  await socket.server({ type: "auth_failed" });
  assert.equal(statuses.at(-1), "auth_failed");
  assert.deepEqual(timers.delays, []);
});

test("stop does not reconnect", () => {
  const { connection, timers } = setup();
  connection.stop();
  assert.deepEqual(timers.delays, []);
  assert.equal(connection.isActive, false);
});

test("a late close from a replaced socket is ignored", async () => {
  const { connection, socket, timers } = setup();
  socket.close();
  timers.runNext();
  const delays = timers.delays.length;
  socket.onclose();
  assert.equal(timers.delays.length, delays);
  assert.equal(connection.isActive, true);
});

test("sync with send_dom navigates, then sends the page before the result", async () => {
  const visited = [];
  const { socket } = await setupConnected({ navigate: async (url) => visited.push(url) });
  await socket.server({ type: "sync_url", session_id: 4, url: "https://jobs.example/1", send_dom: true });
  assert.deepEqual(visited, ["https://jobs.example/1"]);
  assert.deepEqual(socket.sent.map((m) => m.type), ["url", "dom", "sync_result"]);
  assert.equal(socket.sent[1].session_id, 4);
  assert.equal(socket.sent[2].ok, true);
});

test("sync without send_dom does not capture the page", async () => {
  const { socket } = await setupConnected({ capture: async () => assert.fail("captured") });
  await socket.server({ type: "sync_url", session_id: 4, url: "https://jobs.example/1", send_dom: false });
  assert.deepEqual(socket.sent.map((m) => m.type), ["url", "sync_result"]);
});

test("a failed navigation is reported with its reason", async () => {
  const { socket } = await setupConnected({ navigate: async () => { throw new Error("timeout"); } });
  await socket.server({ type: "sync_url", session_id: 4, url: "https://x.example/", send_dom: true });
  assert.deepEqual(socket.sent, [{ type: "sync_result", session_id: 4, ok: false, error: "timeout" }]);
});

test("a failed capture reports failure", async () => {
  const { socket } = await setupConnected({ capture: async () => { throw new Error("blocked"); } });
  await socket.server({ type: "get_dom", session_id: 4 });
  assert.deepEqual(socket.sent, [{ type: "sync_result", session_id: 4, ok: false, error: "blocked" }]);
});

test("a failed capture during sync never also reports success", async () => {
  const { socket } = await setupConnected({ capture: async () => { throw new Error("blocked"); } });
  await socket.server({ type: "sync_url", session_id: 4, url: "https://x.example/", send_dom: true });
  assert.deepEqual(socket.sent.filter((m) => m.type === "sync_result").map((m) => m.ok), [false]);
});

test("fill returns the page's results", async () => {
  const seen = [];
  const { socket } = await setupConnected({
    apply: async (actions, resume) => {
      seen.push(actions, resume);
      return [{ selector: "#a", ok: true }];
    },
  });
  const actions = [{ op: "fill", selector: "#a", value: "x" }];
  const resume = { filename: "a.pdf", base64: "AA==" };
  await socket.server({ type: "fill", plan_id: 9, actions, resume });
  assert.deepEqual(seen, [actions, resume]);
  assert.deepEqual(socket.sent, [{ type: "fill_result", plan_id: 9, results: [{ selector: "#a", ok: true }] }]);
});

test("fill that cannot reach the page fails every action", async () => {
  const { socket } = await setupConnected({ apply: async () => { throw new Error("tab closed"); } });
  await socket.server({ type: "fill", plan_id: 9, actions: [{ op: "fill", selector: "#a", label: "A" }] });
  assert.deepEqual(socket.sent[0].results, [{ selector: "#a", op: "fill", label: "A", ok: false, error: "tab closed" }]);
});

test("ignores invalid JSON and unknown commands", async () => {
  const { socket } = await setupConnected();
  await socket.onmessage({ data: "{nope" });
  await socket.server({ type: "mystery" });
  assert.deepEqual(socket.sent, []);
});
