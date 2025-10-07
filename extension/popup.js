import { signIn, signUp } from "./src/api.js";

const element = (id) => document.getElementById(id);
const STATUS_TEXT = {
  connecting: "Connecting to the server…",
  connected: "Connected",
  disconnected: "Disconnected. Retrying…",
  auth_failed: "Your session ended. Please sign in again.",
  signed_out: "Not signed in",
};

function showMessage(text) {
  element("message").textContent = text;
  element("message").hidden = !text;
}

async function render() {
  const { token, email, serverUrl } = await chrome.storage.local.get(["token", "email", "serverUrl"]);
  const { status } = await chrome.storage.session.get("status");
  element("status").textContent = STATUS_TEXT[status] || "";
  element("signed-in").hidden = !token;
  element("signed-out").hidden = Boolean(token);
  element("account").textContent = email || "";
  if (serverUrl && !element("server").value) element("server").value = serverUrl;
}

function serverAddress() {
  const value = element("server").value.trim();
  if (!/^https?:\/\//i.test(value)) throw new Error("Enter the server address, starting with http://");
  return value;
}

async function startSession(serverUrl, account) {
  await chrome.storage.local.set({ serverUrl, token: account.token, email: account.email });
  await chrome.runtime.sendMessage({ type: "session_changed" });
}

function onSubmit(form, submit) {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showMessage("");
    const button = form.querySelector("button");
    button.disabled = true;
    try {
      await submit(new FormData(form));
      form.reset();
    } catch (error) {
      showMessage(error.message);
    } finally {
      button.disabled = false;
      await render();
    }
  });
}

onSubmit(element("sign-in-form"), async (data) => {
  const server = serverAddress();
  await startSession(server, await signIn(server, data.get("email"), data.get("password")));
});

onSubmit(element("sign-up-form"), async (data) => {
  const server = serverAddress();
  await startSession(server, await signUp(server, data));
});

element("sign-out").addEventListener("click", async () => {
  await chrome.storage.local.remove(["token", "email"]);
  await chrome.runtime.sendMessage({ type: "session_changed" });
  await render();
});

chrome.storage.onChanged.addListener(render);
render();
