// Server-side helper for talking to the engine API.
// The engine is the source of truth; this app is just a client of it.

export const ENGINE_URL = process.env.ENGINE_URL ?? "http://localhost:8000";

export async function engineFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${ENGINE_URL}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`Engine ${resp.status} on ${path}: ${body}`);
  }
  return resp.json() as Promise<T>;
}
