const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export function openMirrorStream() {
  return new EventSource(`${API_BASE}/stream`);
}

