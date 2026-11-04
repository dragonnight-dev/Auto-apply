const KEY = "auto-apply-token";

// Storage can be blocked by the browser; the console then works until the tab reloads.
export function loadToken() {
  try {
    return localStorage.getItem(KEY) || "";
  } catch {
    return "";
  }
}

export function saveToken(token) {
  try {
    if (token) localStorage.setItem(KEY, token);
    else localStorage.removeItem(KEY);
  } catch {
    /* see above */
  }
}
