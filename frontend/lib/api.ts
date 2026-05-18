const PUBLIC_API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "/api";
const SERVER_API_BASE = process.env.BACKEND_INTERNAL_URL ?? PUBLIC_API_BASE;

function apiBase() {
  return typeof window === "undefined" ? SERVER_API_BASE : PUBLIC_API_BASE;
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API ${path} failed: ${response.status}`);
  }
  return response.json();
}
