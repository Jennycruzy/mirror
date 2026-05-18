const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "/api";

export function openMirrorStream() {
  return new EventSource(`${API_BASE}/stream`);
}
