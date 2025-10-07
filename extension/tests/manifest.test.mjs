import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { test } from "node:test";

const here = (path) => new URL(`../${path}`, import.meta.url);
const manifest = JSON.parse(readFileSync(here("manifest.json"), "utf8"));

test("manifest is Manifest V3 and every referenced file exists", () => {
  assert.equal(manifest.manifest_version, 3);
  for (const file of [manifest.background.service_worker, manifest.action.default_popup]) {
    assert.ok(existsSync(here(file)), file);
  }
});

test("popup references existing files and no remote code", () => {
  const html = readFileSync(here("popup.html"), "utf8");
  const references = [...html.matchAll(/(?:src|href)="([^"]+)"/g)].map((match) => match[1]);
  assert.deepEqual(references.sort(), ["popup.css", "popup.js"]);
  references.forEach((file) => assert.ok(existsSync(here(file)), file));
});

test("the controller path used by the adapter exists", () => {
  const source = readFileSync(here("src/browser.js"), "utf8");
  const [, path] = source.match(/CONTROLLER = "([^"]+)"/);
  assert.ok(existsSync(here(path)));
});

test("the socket keepalive needs Chrome 116 or newer", () => {
  assert.ok(Number(manifest.minimum_chrome_version) >= 116);
});
