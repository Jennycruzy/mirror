export const dynamic = "force-dynamic";

export async function GET() {
  const backend = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
  return fetch(`${backend}/stream`);
}

