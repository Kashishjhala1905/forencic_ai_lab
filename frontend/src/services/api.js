import axios from "axios";

// Base URL has NO "/api" suffix: every endpoint path below already starts with /api.
export const API_BASE = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");
const KEY = "fal_token";

export const tokenStore = {
  get: () => localStorage.getItem(KEY),
  set: (t) => localStorage.setItem(KEY, t),
  clear: () => localStorage.removeItem(KEY),
};

export const api = axios.create({ baseURL: API_BASE, timeout: 60000 });

api.interceptors.request.use((cfg) => {
  const t = tokenStore.get();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const url = err.config?.url || "";
    if (err.response?.status === 401 && !url.includes("/api/auth/login") && !url.includes("/api/auth/register")) {
      tokenStore.clear();
      window.dispatchEvent(new Event("fal:unauthorized"));
    }
    return Promise.reject(err);
  }
);

/** Human-readable message for any axios error. Never pretends success. */
export function errMsg(e) {
  if (e?.response) {
    const m = e.response.data?.error?.message;
    return typeof m === "string" && m ? m : `Request failed (HTTP ${e.response.status}).`;
  }
  if (e?.code === "ECONNABORTED") return "The server took too long to respond.";
  return `Cannot reach the backend at ${API_BASE}. Make sure it is running and CORS_ORIGINS allows this site.`;
}

export const get = (url, params) => api.get(url, { params }).then((r) => r.data);

export async function blobUrl(path) {
  const r = await api.get(path, { responseType: "blob" });
  return URL.createObjectURL(r.data);
}

export async function downloadReport(analysisId, filename = "forensic-report.pdf") {
  const r = await api.get(`/api/analysis/${analysisId}/report`, { responseType: "blob" });
  const url = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
