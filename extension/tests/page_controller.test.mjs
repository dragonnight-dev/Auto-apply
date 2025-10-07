import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { JSDOM } from "jsdom";

const source = readFileSync(new URL("../src/page_controller.js", import.meta.url), "utf8");

function load(html) {
  const dom = new JSDOM(`<!doctype html><title>Job</title><body>${html}</body>`, {
    url: "https://jobs.example.com/1",
    runScripts: "outside-only",
  });
  dom.window.eval(source);
  // Results cross a boundary as JSON in Chrome too; this also strips jsdom's realm from the arrays.
  const copy = (value) => JSON.parse(JSON.stringify(value));
  const inner = dom.window.AutoApplyPage;
  const page = {
    capture: () => copy(inner.capture()),
    apply: (actions, resume) => copy(inner.apply(actions, resume)),
  };
  return { page, document: dom.window.document, window: dom.window };
}

const fieldOf = (page, label) => page.capture().fields.find((f) => f.label === label);
const action = (op, selector, value) => ({ op, selector, value, label: "x" });

test("captures labels from for, wrapping, aria-label and aria-labelledby", () => {
  const { page } = load(`
    <label for="a">First name</label><input id="a">
    <label>Email <input name="mail" type="email" required></label>
    <input aria-label="City" name="c">
    <span id="l">Phone</span><input aria-labelledby="l" type="tel" name="t">`);
  const fields = page.capture().fields;
  assert.deepEqual(fields.map((f) => f.label), ["First name", "Email", "City", "Phone"]);
  assert.equal(fields[1].type, "email");
  assert.equal(fields[1].required, true);
});

test("never captures password, hidden, disabled or invisible inputs", () => {
  const { page } = load(`
    <input type="password" name="p"><input type="hidden" name="h">
    <input name="d" disabled><input name="r" readonly>
    <div style="display:none"><input name="n"></div>
    <input name="v" style="visibility:hidden">`);
  assert.deepEqual(page.capture().fields, []);
});

test("never captures what a person typed", () => {
  const { page, document } = load(`<label>Note <input id="a" value="private-default"></label>
    <textarea name="t">private-text</textarea>`);
  document.querySelector("#a").value = "private-typed";
  const fields = JSON.stringify(page.capture().fields);
  assert.ok(!fields.includes("private"));
});

test("keeps hidden file inputs, because styled upload widgets hide them", () => {
  const { page } = load(`<input type="file" name="resume" style="display:none">`);
  assert.equal(page.capture().fields[0].type, "file");
});

test("captures select options, skipping placeholders", () => {
  const { page } = load(`<label>Country <select id="s">
    <option value="">Choose</option><option value="us">USA</option><option value="x" disabled>X</option>
    </select></label>`);
  assert.deepEqual(fieldOf(page, "Country").options, [{ value: "us", label: "USA" }]);
});

test("groups radios into one field with per-option selectors", () => {
  const { page, document } = load(`<fieldset><legend>Remote?</legend>
    <label><input type="radio" name="r" value="y">Yes</label>
    <label><input type="radio" name="r" value="n">No</label></fieldset>`);
  const field = fieldOf(page, "Remote?");
  assert.equal(page.capture().fields.length, 1);
  assert.deepEqual(field.options.map((o) => o.label), ["Yes", "No"]);
  assert.equal(document.querySelector(field.options[1].selector).value, "n");
});

test("builds selectors that find the element, including awkward ids and no attributes", () => {
  const { page, document } = load(`
    <input id='we"ird:id' aria-label="A">
    <input id="dup" aria-label="B"><input id="dup" aria-label="C">
    <div><div><input aria-label="D"></div><div><input aria-label="E"></div></div>`);
  for (const field of page.capture().fields) {
    assert.equal(document.querySelector(field.selector).getAttribute("aria-label"), field.label);
  }
});

test("captures buttons and page text", () => {
  const { page } = load(`<p>We build things</p><button id="go" type="submit">Apply now</button>
    <input type="submit" value="Send" name="s"><button disabled>Off</button>`);
  const captured = page.capture();
  assert.deepEqual(captured.buttons.map((b) => b.text), ["Apply now", "Send"]);
  assert.match(captured.text, /We build things/);
  assert.equal(captured.url, "https://jobs.example.com/1");
  assert.equal(captured.title, "Job");
});

test("fill sets the value and fires the events frameworks listen to", () => {
  const { page, document } = load(`<input id="a"><textarea id="b"></textarea>`);
  const events = [];
  for (const name of ["input", "change"]) document.addEventListener(name, (e) => events.push(name + e.target.id));
  const results = page.apply([action("fill", "#a", "one"), action("fill", "#b", "two")]);
  assert.ok(results.every((r) => r.ok));
  assert.equal(document.querySelector("#a").value, "one");
  assert.equal(document.querySelector("#b").value, "two");
  assert.deepEqual(events, ["inputa", "changea", "inputb", "changeb"]);
});

test("fill reaches past a framework's value override", () => {
  const { page, document } = load(`<input id="a">`);
  const element = document.querySelector("#a");
  let tracked = "";
  // React shadows `value` on the node in the same way.
  Object.defineProperty(element, "value", {
    configurable: true,
    get: () => Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), "value").get.call(element),
    set: (v) => { tracked = v; },
  });
  assert.equal(page.apply([action("fill", "#a", "typed")])[0].ok, true);
  assert.equal(tracked, "");
});

test("refuses to fill password, hidden and file inputs", () => {
  const { page, document } = load(`<input id="p" type="password"><input id="h" type="hidden"><input id="f" type="file">`);
  const results = page.apply([action("fill", "#p", "x"), action("fill", "#h", "x"), action("fill", "#f", "x")]);
  assert.deepEqual(results.map((r) => r.error), ["forbidden_field", "forbidden_field", "forbidden_field"]);
  assert.equal(document.querySelector("#p").value, "");
});

test("select, check and click", () => {
  const { page, document } = load(`<select id="s"><option value="a">A</option><option value="b">B</option></select>
    <input id="c" type="checkbox"><input id="r" type="radio" name="g"><button id="b">Go</button>`);
  let clicked = 0;
  document.querySelector("#b").addEventListener("click", () => { clicked += 1; });
  const results = page.apply([action("select", "#s", "b"), action("check", "#c"), action("check", "#r"), action("click", "#b")]);
  assert.ok(results.every((r) => r.ok));
  assert.equal(document.querySelector("#s").value, "b");
  assert.equal(document.querySelector("#c").checked, true);
  assert.equal(document.querySelector("#r").checked, true);
  assert.equal(clicked, 1);
});

test("check leaves an already ticked box ticked", () => {
  const { page, document } = load(`<input id="c" type="checkbox" checked>`);
  assert.equal(page.apply([action("check", "#c")])[0].ok, true);
  assert.equal(document.querySelector("#c").checked, true);
});

test("one failing action does not stop the others and failures are named", () => {
  const { page, document } = load(`<select id="s"><option value="a">A</option></select><input id="a">`);
  const results = page.apply([
    action("fill", "#missing", "x"),
    action("select", "#s", "nope"),
    action("fill", "##bad selector", "x"),
    action("evil", "#a", "x"),
    action("constructor", "#a", "x"),
    action("check", "#a"),
    action("fill", "#a", "still works"),
  ]);
  assert.deepEqual(results.slice(0, 2).map((r) => r.error), ["not_found", "option_missing"]);
  assert.equal(results[2].ok, false);
  assert.deepEqual(results.slice(3, 6).map((r) => r.error), ["unknown_operation", "unknown_operation", "not_checkable"]);
  assert.equal(results[6].ok, true);
  assert.equal(document.querySelector("#a").value, "still works");
});

test("upload attaches the resume as a named PDF", () => {
  const { page, document, window } = load(`<input id="f" type="file">`);
  const added = [];
  window.DataTransfer = class {
    constructor() {
      this.files = { list: added };
      this.items = { add: (file) => added.push(file) };
    }
  };
  const element = document.querySelector("#f");
  let assigned = null;
  Object.defineProperty(element, "files", { set: (v) => { assigned = v; } });
  let changed = 0;
  element.addEventListener("change", () => { changed += 1; });

  const base64 = Buffer.from("%PDF-1.4").toString("base64");
  window.atob = globalThis.atob;
  const [result] = page.apply([action("upload", "#f")], { filename: "Ann_Lee.pdf", base64 });

  assert.equal(result.ok, true);
  assert.equal(assigned.list[0].name, "Ann_Lee.pdf");
  assert.equal(assigned.list[0].type, "application/pdf");
  assert.equal(assigned.list[0].size, 8);
  assert.equal(changed, 1);
});

test("upload fails clearly without a resume or on the wrong element", () => {
  const { page } = load(`<input id="f" type="file"><input id="t">`);
  const results = page.apply([action("upload", "#f"), action("upload", "#t")], null);
  assert.deepEqual(results.map((r) => r.error), ["no_resume", "not_a_file_input"]);
});
