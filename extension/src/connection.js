// The extension's WebSocket to the server: authenticates, reconnects, and runs server commands.
const MAX_BACKOFF_MS = 30000;
const KEEPALIVE_MS = 20000; // Socket traffic keeps a Manifest V3 service worker alive.

export function toWebSocketUrl(serverUrl) {
  const url = new URL(serverUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/client/";
  url.search = "";
  url.hash = "";
  return url.toString();
}

const describeError = (error) => (error && error.message) || String(error);

export class ClientConnection {
  constructor({ serverUrl, token, browser, WebSocketImpl, onStatus = () => {}, timers = globalThis }) {
    this.url = toWebSocketUrl(serverUrl);
    this.token = token;
    this.browser = browser;
    this.WebSocketImpl = WebSocketImpl;
    this.onStatus = onStatus;
    this.timers = timers;
    this.socket = null;
    this.stopped = false;
    this.authenticated = false;
    this.attempts = 0;
    this.retryTimer = null;
    this.keepalive = null;
  }

  start() {
    this.stopped = false;
    this.open();
  }

  stop() {
    this.stopped = true;
    this.timers.clearTimeout(this.retryTimer);
    this.timers.clearInterval(this.keepalive);
    this.socket?.close();
    this.socket = null;
    this.authenticated = false;
  }

  get isActive() {
    return !this.stopped && this.socket !== null;
  }

  open() {
    this.onStatus("connecting");
    let socket;
    try {
      socket = new this.WebSocketImpl(this.url);
    } catch {
      this.socket = null;
      this.scheduleRetry();
      return;
    }
    this.socket = socket;
    socket.onopen = () => this.send({ type: "auth", token: this.token });
    socket.onmessage = (event) => this.receive(event.data);
    socket.onclose = () => this.closed(socket);
  }

  closed(socket) {
    if (socket !== this.socket) return;
    this.socket = null;
    this.authenticated = false;
    this.timers.clearInterval(this.keepalive);
    if (!this.stopped) {
      this.onStatus("disconnected");
      this.scheduleRetry();
    }
  }

  scheduleRetry() {
    const delay = Math.min(1000 * 2 ** this.attempts, MAX_BACKOFF_MS);
    this.attempts += 1;
    this.retryTimer = this.timers.setTimeout(() => this.open(), delay);
  }

  send(message) {
    if (this.socket && this.socket.readyState === this.WebSocketImpl.OPEN) {
      this.socket.send(JSON.stringify(message));
    }
  }

  reportUrl(url) {
    if (this.authenticated && url) this.send({ type: "url", url });
  }

  async receive(raw) {
    let message;
    try {
      message = JSON.parse(raw);
    } catch {
      return;
    }
    await this.handle(message);
  }

  async handle(message) {
    switch (message.type) {
      case "auth_ok":
        this.authenticated = true;
        this.attempts = 0;
        this.onStatus("connected");
        this.keepalive = this.timers.setInterval(() => this.send({ type: "ping" }), KEEPALIVE_MS);
        break;
      case "auth_failed":
        // The token is bad, so retrying cannot help. The person has to sign in again.
        this.stop();
        this.onStatus("auth_failed");
        break;
      case "get_url":
        this.reportUrl(await this.browser.activeUrl().catch(() => ""));
        break;
      case "get_dom":
        await this.sendDom(message.session_id);
        break;
      case "sync_url":
        await this.sync(message);
        break;
      case "fill":
        await this.fill(message);
        break;
      default:
        break;
    }
  }

  async sync({ session_id: sessionId, url, send_dom: sendDom }) {
    try {
      await this.browser.navigate(url);
    } catch (error) {
      this.send({ type: "sync_result", session_id: sessionId, ok: false, error: describeError(error) });
      return;
    }
    this.reportUrl(url);
    // A failed capture has already reported ok: false.
    if (!sendDom || (await this.sendDom(sessionId))) {
      this.send({ type: "sync_result", session_id: sessionId, ok: true });
    }
  }

  async sendDom(sessionId) {
    try {
      this.send({ type: "dom", session_id: sessionId, dom: await this.browser.capture() });
      return true;
    } catch (error) {
      this.send({ type: "sync_result", session_id: sessionId, ok: false, error: describeError(error) });
      return false;
    }
  }

  async fill({ plan_id: planId, actions, resume }) {
    let results;
    try {
      results = await this.browser.apply(actions, resume);
    } catch (error) {
      results = actions.map((action) => ({
        selector: action.selector, op: action.op, label: action.label, ok: false, error: describeError(error),
      }));
    }
    this.send({ type: "fill_result", plan_id: planId, results });
  }
}
