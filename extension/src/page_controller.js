// Injected into the job page. Reads the form's structure (never the values people typed)
// and applies fill actions from the server. Classic script: exposes one global.
(() => {
  const MAX_TEXT = 20000;
  const IGNORED_INPUTS = new Set(["password", "hidden", "submit", "button", "reset", "image"]);
  const BUTTON_INPUTS = new Set(["submit", "button"]);
  const FORBIDDEN_FILL = new Set(["password", "hidden", "file"]);

  const quote = (value) => `"${String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
  const clean = (text) => (text || "").replace(/\s+/g, " ").trim();

  function isUnique(root, selector) {
    try {
      return root.querySelectorAll(selector).length === 1;
    } catch {
      return false;
    }
  }

  function buildSelector(element) {
    const root = element.ownerDocument;
    const tag = element.tagName.toLowerCase();
    if (element.id && isUnique(root, `[id=${quote(element.id)}]`)) return `[id=${quote(element.id)}]`;
    const name = element.getAttribute("name");
    if (name && isUnique(root, `${tag}[name=${quote(name)}]`)) return `${tag}[name=${quote(name)}]`;
    if (name && element.getAttribute("value") !== null) {
      const selector = `${tag}[name=${quote(name)}][value=${quote(element.getAttribute("value"))}]`;
      if (isUnique(root, selector)) return selector;
    }
    const parts = [];
    for (let node = element; node && node.nodeType === 1 && node !== root.documentElement; node = node.parentElement) {
      const siblings = node.parentElement
        ? [...node.parentElement.children].filter((child) => child.tagName === node.tagName)
        : [node];
      parts.unshift(`${node.tagName.toLowerCase()}:nth-of-type(${siblings.indexOf(node) + 1})`);
    }
    return parts.join(" > ");
  }

  function labelOf(element) {
    const root = element.ownerDocument;
    if (element.labels && element.labels.length) {
      // A wrapping label also contains the control, and a select's options would pollute its text.
      const label = element.labels[0].cloneNode(true);
      label.querySelectorAll("input, select, textarea").forEach((control) => control.remove());
      return clean(label.textContent);
    }
    const aria = element.getAttribute("aria-label");
    if (aria) return clean(aria);
    const labelledBy = element.getAttribute("aria-labelledby");
    if (labelledBy) {
      return clean(labelledBy.split(/\s+/).map((id) => root.getElementById(id)?.textContent || "").join(" "));
    }
    return "";
  }

  function groupLabelOf(element) {
    const fieldset = element.closest("fieldset");
    const legend = fieldset && fieldset.querySelector("legend");
    if (legend) return clean(legend.textContent);
    const group = element.closest('[role="radiogroup"]');
    return group ? labelOf(group) : "";
  }

  function isVisible(element) {
    const view = element.ownerDocument.defaultView;
    for (let node = element; node && node.nodeType === 1; node = node.parentElement) {
      const style = view.getComputedStyle(node);
      if (style.display === "none" || style.visibility === "hidden") return false;
    }
    return true;
  }

  function describe(element, type) {
    return {
      selector: buildSelector(element),
      type,
      label: labelOf(element),
      name: element.getAttribute("name") || "",
      placeholder: element.getAttribute("placeholder") || "",
      required: element.required === true || element.getAttribute("aria-required") === "true",
      options: [],
    };
  }

  function capture(root) {
    const fields = [];
    const radioGroups = new Map();

    for (const element of root.querySelectorAll("input, textarea, select")) {
      if (element.disabled || element.readOnly) continue;
      const tag = element.tagName.toLowerCase();
      const type = tag === "input" ? (element.getAttribute("type") || "text").toLowerCase() : tag;
      if (IGNORED_INPUTS.has(type)) continue;
      // Styled upload widgets usually hide the real file input.
      if (type !== "file" && !isVisible(element)) continue;

      if (type === "radio") {
        const key = element.name || buildSelector(element);
        if (!radioGroups.has(key)) {
          const field = describe(element, "radio");
          field.label = groupLabelOf(element) || element.name || "";
          radioGroups.set(key, field);
          fields.push(field);
        }
        radioGroups.get(key).options.push({
          value: element.value,
          label: labelOf(element) || element.value,
          selector: buildSelector(element),
        });
      } else if (type === "select") {
        const field = describe(element, "select");
        field.options = [...element.options]
          .filter((option) => option.value !== "" && !option.disabled)
          .map((option) => ({ value: option.value, label: clean(option.textContent) }));
        fields.push(field);
      } else {
        fields.push(describe(element, type));
      }
    }

    const buttons = [];
    for (const element of root.querySelectorAll('button, input, [role="button"]')) {
      if (element.tagName === "INPUT" && !BUTTON_INPUTS.has((element.getAttribute("type") || "").toLowerCase())) continue;
      if (element.disabled || !isVisible(element)) continue;
      buttons.push({
        selector: buildSelector(element),
        text: clean(element.textContent) || element.value || element.getAttribute("aria-label") || "",
        type: (element.getAttribute("type") || "").toLowerCase(),
      });
    }

    return {
      url: root.location ? root.location.href : "",
      title: root.title || "",
      text: clean(root.body ? root.body.innerText || root.body.textContent : "").slice(0, MAX_TEXT),
      fields,
      buttons,
    };
  }

  function setNativeValue(element, value) {
    // Frameworks such as React ignore plain assignment; use the prototype's own setter.
    const view = element.ownerDocument.defaultView;
    const proto = element.tagName === "TEXTAREA" ? view.HTMLTextAreaElement.prototype : view.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(element, value);
  }

  function fire(element, ...names) {
    const view = element.ownerDocument.defaultView;
    for (const name of names) element.dispatchEvent(new view.Event(name, { bubbles: true }));
  }

  function base64ToBytes(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }

  const operations = {
    fill(element, action) {
      if (!["INPUT", "TEXTAREA"].includes(element.tagName)) throw new Error("not_a_text_field");
      if (FORBIDDEN_FILL.has((element.getAttribute("type") || "").toLowerCase())) throw new Error("forbidden_field");
      element.focus?.();
      setNativeValue(element, action.value);
      fire(element, "input", "change", "blur");
      if (element.value !== action.value) throw new Error("value_rejected");
    },
    select(element, action) {
      if (element.tagName !== "SELECT") throw new Error("not_a_select");
      element.value = action.value;
      if (element.value !== action.value) throw new Error("option_missing");
      fire(element, "input", "change");
    },
    check(element) {
      if (!["checkbox", "radio"].includes((element.getAttribute("type") || "").toLowerCase())) {
        throw new Error("not_checkable");
      }
      if (!element.checked) element.click();
      if (!element.checked) throw new Error("not_checked");
    },
    upload(element, _action, resume, view) {
      if ((element.getAttribute("type") || "").toLowerCase() !== "file") throw new Error("not_a_file_input");
      if (!resume) throw new Error("no_resume");
      const file = new view.File([base64ToBytes(resume.base64)], resume.filename, { type: "application/pdf" });
      const transfer = new view.DataTransfer();
      transfer.items.add(file);
      element.files = transfer.files;
      fire(element, "input", "change");
    },
    click(element) {
      element.click();
    },
  };

  function apply(root, actions, resume) {
    const view = root.defaultView;
    return actions.map((action) => {
      const result = { selector: action.selector, op: action.op, label: action.label || "", ok: false };
      try {
        const operation = Object.hasOwn(operations, action.op) ? operations[action.op] : null;
        if (!operation) throw new Error("unknown_operation");
        const element = root.querySelector(action.selector);
        if (!element) throw new Error("not_found");
        operation(element, action, resume, view);
        result.ok = true;
      } catch (error) {
        result.error = error.message;
      }
      return result;
    });
  }

  globalThis.AutoApplyPage = {
    capture: () => capture(document),
    apply: (actions, resume) => apply(document, actions, resume),
  };
})();
