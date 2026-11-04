import { ClientConnection } from "./src/connection.js";
import { createBrowser } from "./src/browser.js";

const browser = createBrowser(chrome);
let connection = null;

const setStatus = (status) => chrome.storage.session.set({ status });

async function connect() {
  const { token, serverUrl } = await chrome.storage.local.get(["token", "serverUrl"]);
  // Stop only after the await: overlapping calls then each replace the previous socket.
  connection?.stop();
  connection = null;
  if (!token || !serverUrl) {
    await setStatus("signed_out");
    return;
  }
  connection = new ClientConnection({
    serverUrl,
    token,
    browser,
    WebSocketImpl: WebSocket,
    onStatus: (status) => {
      setStatus(status);
      if (status === "auth_failed") chrome.storage.local.remove("token");
    },
  });
  connection.start();
}

async function reportActiveUrl() {
  if (connection) connection.reportUrl(await browser.activeUrl());
}

chrome.runtime.onInstalled.addListener(connect);
chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onMessage.addListener((message, _sender, reply) => {
  if (message.type === "session_changed") {
    connect().then(() => reply({ ok: true }));
    return true;
  }
  return false;
});

chrome.tabs.onActivated.addListener(reportActiveUrl);
chrome.tabs.onUpdated.addListener((_tabId, change, tab) => {
  if (change.status === "complete" && tab.active) reportActiveUrl();
});

// Chrome may end the service worker; this alarm restarts it and restores the socket.
chrome.alarms.create("watchdog", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener(() => {
  if (!connection?.isActive) connect();
});

connect();
