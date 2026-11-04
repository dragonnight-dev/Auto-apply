// HTTP calls made by the popup before a socket exists.
async function request(serverUrl, path, options) {
  let response;
  try {
    response = await fetch(new URL(path, serverUrl), options);
  } catch {
    throw new Error("Cannot reach the server. Check its address.");
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `The server replied with ${response.status}.`);
  return body;
}

export function signIn(serverUrl, email, password) {
  return request(serverUrl, "/api/clients/signin", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function signUp(serverUrl, formData) {
  return request(serverUrl, "/api/clients/signup", { method: "POST", body: formData });
}
