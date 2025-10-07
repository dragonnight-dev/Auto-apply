// Chrome adapter. Syncing uses one dedicated work tab, so the person's other tabs are left alone.
const CONTROLLER = "src/page_controller.js";
const WORK_TAB_KEY = "workTabId";
const LOAD_TIMEOUT_MS = 45000;
const SETTLE_MS = 1500; // Single-page apps render their forms after the load event.

const isHttp = (url) => /^https?:\/\//i.test(url || "");

export function createBrowser(chrome, { loadTimeoutMs = LOAD_TIMEOUT_MS, settleMs = SETTLE_MS } = {}) {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  async function workTab() {
    const stored = await chrome.storage.session.get(WORK_TAB_KEY);
    const tabId = stored[WORK_TAB_KEY];
    if (tabId === undefined) return null;
    try {
      return await chrome.tabs.get(tabId);
    } catch {
      return null; // the person closed it
    }
  }

  function waitForLoad(tabId) {
    return new Promise((resolve, reject) => {
      const finish = (settle, value) => {
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(listener);
        settle(value);
      };
      const timer = setTimeout(() => finish(reject, new Error("The page took too long to load.")), loadTimeoutMs);
      const listener = (updatedId, change) => {
        if (updatedId === tabId && change.status === "complete") finish(resolve);
      };
      chrome.tabs.onUpdated.addListener(listener);
    });
  }

  async function runInPage(func, args) {
    const tab = await workTab();
    if (!tab) throw new Error("The work tab is closed. Sync the URL again.");
    const target = { tabId: tab.id };
    await chrome.scripting.executeScript({ target, files: [CONTROLLER] });
    const [frame] = await chrome.scripting.executeScript({ target, func, args });
    return frame.result;
  }

  return {
    async activeUrl() {
      const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      return tab && isHttp(tab.url) ? tab.url : "";
    },

    async navigate(url) {
      if (!isHttp(url)) throw new Error("Only http and https pages can be opened.");
      const existing = await workTab();
      // Listen before anything else can yield, so a fast load cannot be missed.
      let loaded;
      let tab;
      if (existing) {
        loaded = waitForLoad(existing.id);
        tab = await chrome.tabs.update(existing.id, { url, active: true });
      } else {
        tab = await chrome.tabs.create({ url, active: true });
        loaded = waitForLoad(tab.id);
        await chrome.storage.session.set({ [WORK_TAB_KEY]: tab.id });
      }
      await loaded;
      await sleep(settleMs);
      return tab;
    },

    capture() {
      return runInPage(() => globalThis.AutoApplyPage.capture(), []);
    },

    apply(actions, resume) {
      return runInPage((a, r) => globalThis.AutoApplyPage.apply(a, r), [actions, resume ?? null]);
    },
  };
}
