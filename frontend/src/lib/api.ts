// Typed API client. All calls include credentials (cookies) so JWT auth flows naturally.

/** Same-origin `/api/v1` keeps cookies/CORS correct whether users hit LAN IP or the real hostname (docker-compose.prod.yml passes this default). */
function normalizeApiBase(raw: string | undefined): string {
  const fallback = "http://localhost:8000/api/v1";
  if (raw === undefined || raw === "") return fallback;
  const trimmed = raw.trim();
  if (trimmed.startsWith("/")) return trimmed.endsWith("/") ? trimmed.slice(0, -1) : trimmed;
  return trimmed.endsWith("/") ? trimmed.slice(0, -1) : trimmed;
}

export const API_BASE = normalizeApiBase(process.env.NEXT_PUBLIC_API_BASE_URL);

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

type FetchOptions = Omit<RequestInit, "body"> & { body?: unknown };

async function request<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { body, headers, ...rest } = options;
  const init: RequestInit = {
    credentials: "include",
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(headers ?? {}),
    },
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const res = await fetch(url, init);

  if (res.status === 204) {
    return undefined as T;
  }

  let payload: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!res.ok) {
    const detail =
      (typeof payload === "object" && payload && "detail" in payload
        ? (payload as { detail: unknown }).detail
        : payload) ?? res.statusText;
    throw new ApiError(res.status, String(detail), payload);
  }

  return payload as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: async <T>(path: string, file: File): Promise<T> => {
    const fd = new FormData();
    fd.append("file", file);
    const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
    const res = await fetch(url, {
      method: "POST",
      credentials: "include",
      body: fd,
    });
    const text = await res.text();
    let payload: unknown = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = text;
      }
    }
    if (!res.ok) {
      throw new ApiError(res.status, String((payload as { detail?: string })?.detail ?? res.statusText), payload);
    }
    return payload as T;
  },
};

export const API_PUBLIC_BASE = API_BASE.startsWith("http")
  ? API_BASE.replace(/\/api\/v1\/?$/, "")
  : "";
