const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(API_BASE + path, {
    headers: { Accept: "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status}: ${detail || response.statusText}`);
  }
  return response.json();
}

export const api = {
  health: () => request("/health"),
  adminUnits: () => request("/api/v1/admin-units"),
  habitations: (params = "") => request("/api/v1/habitations" + params),
  habitation: (id) => request(`/api/v1/habitations/${encodeURIComponent(id)}`),
  hazards: () => request("/api/v1/hazards"),
  riskMap: () => request("/api/v1/risk/map"),
  sites: () => request("/api/v1/sites"),
  siteCapacity: (id) => request(`/api/v1/sites/${encodeURIComponent(id)}/capacity`),
  priorities: () => request("/api/v1/priorities"),
  run: (id) => request(`/api/v1/runs/${encodeURIComponent(id)}`),
  report: (id) => request(`/api/v1/reports/${encodeURIComponent(id)}`),
  optimize: (payload) => request("/api/v1/optimize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }),
};

export { API_BASE };
