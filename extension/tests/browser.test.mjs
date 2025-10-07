import assert from "node:assert/strict";
import { test } from "node:test";
import { createBrowser } from "../src/browser.js";

function fakeChrome({ loads = true, openTabs = [] } = {}) {
  const session = {};
  const listeners = new Set();
  const tabs = new Map(openTabs.map((tab) => [tab.id, tab]));
  const log = { created: [], updated: [], scripts: [] };
  const finishLoad = (id) => {
    if (loads) setTimeout(() => [...listeners].forEach((fn) => fn(id, { status: "complete" })), 0);
  };
  return {
    log,
    listeners,
    storage: {
      session: {
        get: async (key) => (key in session ? { [key]: session[key] } : {}),
        set: async (values) => Object.assign(session, values),
      },
    },
    tabs: {
      onUpdated: { addListener: (fn) => listeners.add(fn), removeListener: (fn) => listeners.delete(fn) },
      get: async (id) => {
        if (!tabs.has(id)) throw new Error("No tab");
        return tabs.get(id);
      },
      query: async () => openTabs.filter((tab) => tab.active),
      create: async ({ url }) => {
        const tab = { id: 50 + log.created.length, url };
        tabs.set(tab.id, tab);
        log.created.push(url);
        finishLoad(tab.id);
        return tab;
      },
      update: async (id, { url }) => {
        log.updated.push([id, url]);
        finishLoad(id);
        return tabs.get(id);
      },
    },
    scripting: {
      executeScript: async (call) => {
        log.scripts.push(call);
        return call.func ? [{ result: { ran: call.args } }] : [{}];
      },
    },
    closeTab: (id) => tabs.delete(id),
  };
}

const quick = { settleMs: 0, loadTimeoutMs: 20 };

test("the first sync opens a work tab and later syncs reuse it", async () => {
  const chrome = fakeChrome();
  const browser = createBrowser(chrome, quick);
  await browser.navigate("https://a.example/");
  await browser.navigate("https://b.example/");
  assert.deepEqual(chrome.log.created, ["https://a.example/"]);
  assert.deepEqual(chrome.log.updated, [[50, "https://b.example/"]]);
  assert.equal(chrome.listeners.size, 0);
});

test("a new work tab replaces one the person closed", async () => {
  const chrome = fakeChrome();
  const browser = createBrowser(chrome, quick);
  await browser.navigate("https://a.example/");
  chrome.closeTab(50);
  await browser.navigate("https://b.example/");
  assert.equal(chrome.log.created.length, 2);
});

test("refuses non-http URLs", async () => {
  const chrome = fakeChrome();
  const browser = createBrowser(chrome, quick);
  for (const url of ["javascript:alert(1)", "chrome://settings", "file:///etc/passwd"]) {
    await assert.rejects(browser.navigate(url), /http and https/);
  }
  assert.deepEqual(chrome.log.created, []);
});

test("a page that never loads times out and removes its listener", async () => {
  const chrome = fakeChrome({ loads: false });
  await assert.rejects(createBrowser(chrome, quick).navigate("https://a.example/"), /too long/);
  assert.equal(chrome.listeners.size, 0);
});

test("capture and apply inject the controller into the work tab", async () => {
  const chrome = fakeChrome();
  const browser = createBrowser(chrome, quick);
  await browser.navigate("https://a.example/");
  await browser.capture();
  const result = await browser.apply([{ op: "click" }]);
  assert.deepEqual(result, { ran: [[{ op: "click" }], null] });
  assert.deepEqual(chrome.log.scripts[0], { target: { tabId: 50 }, files: ["src/page_controller.js"] });
  assert.ok(chrome.log.scripts.every((call) => call.target.tabId === 50));
});

test("capture fails clearly without a work tab", async () => {
  await assert.rejects(createBrowser(fakeChrome(), quick).capture(), /work tab is closed/);
});

test("activeUrl reports only web pages", async () => {
  const web = fakeChrome({ openTabs: [{ id: 1, active: true, url: "https://x.example/" }] });
  assert.equal(await createBrowser(web, quick).activeUrl(), "https://x.example/");
  const internal = fakeChrome({ openTabs: [{ id: 1, active: true, url: "chrome://newtab/" }] });
  assert.equal(await createBrowser(internal, quick).activeUrl(), "");
});
