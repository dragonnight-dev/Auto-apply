export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export async function request(path, { method = "GET", body, token } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`/api/${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Cannot reach the server.", 0);
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(data.error || `The server replied with ${response.status}.`, response.status);
  return data;
}

export const signIn = (username, password) =>
  request("boss/signin", { method: "POST", body: { username, password } });
export const signUp = (username, password, bossKey) =>
  request("boss/signup", { method: "POST", body: { username, password, boss_key: bossKey } });
export const setClientEnabled = (token, id, enabled) =>
  request(`clients/${id}`, { method: "PATCH", body: { enabled }, token });
export const getStatistics = (token) => request("stats", { token });
export const getHistory = (token, clientId) => request(`history?client=${clientId}`, { token });
export const deleteHistoryEntry = (token, id) => request(`history/${id}`, { method: "DELETE", token });
export const clearHistory = (token, clientId) => request(`history?client=${clientId}`, { method: "DELETE", token });
