import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { signIn, signUp } from "../src/api.js";

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

const reply = (status, body) => async (url, options) => {
  reply.last = { url: String(url), options };
  return new Response(JSON.stringify(body), { status });
};

test("sign in posts credentials as JSON", async () => {
  globalThis.fetch = reply(200, { token: "t", email: "a@example.com" });
  assert.equal((await signIn("http://srv:8000", "a@example.com", "pw")).token, "t");
  assert.equal(reply.last.url, "http://srv:8000/api/clients/signin");
  assert.deepEqual(JSON.parse(reply.last.options.body), { email: "a@example.com", password: "pw" });
});

test("sign up sends the form untouched, so the browser sets the multipart boundary", async () => {
  globalThis.fetch = reply(201, { token: "t" });
  const form = new FormData();
  await signUp("http://srv:8000", form);
  assert.equal(reply.last.url, "http://srv:8000/api/clients/signup");
  assert.equal(reply.last.options.body, form);
  assert.equal(reply.last.options.headers, undefined);
});

test("server errors surface their message", async () => {
  globalThis.fetch = reply(401, { error: "Incorrect email or password." });
  await assert.rejects(signIn("http://srv", "a", "b"), /Incorrect email/);
});

test("an unreachable server has a helpful message", async () => {
  globalThis.fetch = async () => { throw new TypeError("failed"); };
  await assert.rejects(signIn("http://srv", "a", "b"), /Cannot reach the server/);
});

test("a non-JSON error still reports its status", async () => {
  globalThis.fetch = async () => new Response("<html>", { status: 502 });
  await assert.rejects(signIn("http://srv", "a", "b"), /502/);
});
