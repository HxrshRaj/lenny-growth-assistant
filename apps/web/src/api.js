const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(status, body) {
    super(body?.detail || `Request failed with status ${status}`);
    this.status = status;
    this.code = body?.code || "UNKNOWN";
    this.body = body;
  }
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let body = null;
  try {
    body = await res.json();
  } catch {
    // no JSON body (e.g. network-level failure before this branch even runs)
  }
  if (!res.ok) {
    throw new ApiError(res.status, body);
  }
  return body;
}

export const api = {
  getHealth: () => request("/health"),
  getConfig: () => request("/config"),
  createSession: (userId = "anonymous") =>
    request("/sessions", { method: "POST", body: JSON.stringify({ user_id: userId }) }),
  getSession: (id) => request(`/sessions/${id}`),
  listMessages: (id) => request(`/sessions/${id}/messages`),
  postMessage: (id, content) =>
    request(`/sessions/${id}/messages`, { method: "POST", body: JSON.stringify({ content }) }),
};

export { ApiError };
