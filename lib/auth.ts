/**
 * Auth token seam (GAP v2 T3-08).
 *
 * Single place the frontend stores/reads the JWT used to talk to the backend.
 * The Logto SDK will call `setAuthToken` on login (Phase 2); until then the
 * token is null and, against DEBUG-mode backends, requests work without one.
 *
 * REST calls send `Authorization: Bearer <jwt>` (see `authHeaders`);
 * WebSockets send `?token=<jwt>` (see `wsAuthQuery`). The backend derives
 * identity from the verified token and ignores client-supplied
 * user_id/user_name query params.
 */

const STORAGE_KEY = "dclaw_token";

let _token: string | null = null;

export function setAuthToken(token: string | null): void {
  _token = token;
  if (typeof window !== "undefined") {
    if (token) {
      sessionStorage.setItem(STORAGE_KEY, token);
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  }
}

export function getAuthToken(): string | null {
  if (_token) return _token;
  if (typeof window !== "undefined") {
    return sessionStorage.getItem(STORAGE_KEY);
  }
  return null;
}

export function authHeaders(): Record<string, string> {
  const t = getAuthToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export function wsAuthQuery(): string {
  const t = getAuthToken();
  return t ? `token=${encodeURIComponent(t)}` : "";
}
