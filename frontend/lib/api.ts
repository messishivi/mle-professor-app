/**
 * Typed client for the MLE Professor API (FastAPI, api.py).
 *
 * Base URL: NEXT_PUBLIC_API_BASE (inlined at build time) or the local
 * dev server. All functions throw ApiError on non-2xx responses.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

// ------------------------------------------------------------- paper types

export interface ApiPaper {
  id: string;
  title: string;
  authors: string;
  published_date: string | null;
  summary_raw: string;
  summary_structured: unknown;
  read_status: 0 | 1;
  added_at: string;
}

export interface PapersResponse {
  count: number;
  papers: ApiPaper[];
}

export interface IngestRequest {
  /** ArXiv categories; omitted = the pipeline default (cs.CL, cs.LG). */
  categories?: string[];
  /** 1..100, default 20 (the UI slider is 5..50 step 5, Streamlit parity). */
  max_results?: number;
}

export interface IngestResult {
  query: string;
  fetched: number;
  upserted: number;
  skipped: number;
  papers: ApiPaper[];
  errors: string[];
}

// ---------------------------------------------------------------- helpers

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch (exc) {
    throw new ApiError(0, `Cannot reach the API at ${API_BASE}`);
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body — keep the status text
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

// ---------------------------------------------------------------- endpoints

export interface PapersQuery {
  q?: string;
  /** undefined = all, 0 = unread, 1 = read (FastAPI int param). */
  read?: 0 | 1;
  limit?: number;
}

export function listPapers(query: PapersQuery = {}): Promise<PapersResponse> {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.read !== undefined) params.set("read", String(query.read));
  if (query.limit !== undefined) params.set("limit", String(query.limit));
  const qs = params.toString();
  return request<PapersResponse>(`/papers${qs ? `?${qs}` : ""}`);
}

export function getPaper(id: string): Promise<ApiPaper> {
  return request<ApiPaper>(`/papers/${encodeURIComponent(id)}`);
}

export function patchPaper(
  id: string,
  read_status: 0 | 1,
): Promise<ApiPaper> {
  return request<ApiPaper>(`/papers/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify({ read_status }),
  });
}

export function ingest(req: IngestRequest = {}): Promise<IngestResult> {
  return request<IngestResult>("/papers/ingest", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
