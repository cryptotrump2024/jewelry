// Proxy: browser → Next.js → engine. Keeps the engine URL server-side and
// avoids CORS. Client components call /api/engine/<engine-path>.

import { NextRequest, NextResponse } from "next/server";
import { ENGINE_URL } from "@/lib/engine";

async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  const target = `${ENGINE_URL}/${path.join("/")}${req.nextUrl.search}`;
  const init: RequestInit = {
    method: req.method,
    headers: { "content-type": "application/json" },
  };
  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.text();
  }
  const resp = await fetch(target, init);
  const body = await resp.text();
  return new NextResponse(body, {
    status: resp.status,
    headers: { "content-type": resp.headers.get("content-type") ?? "application/json" },
  });
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxy(req, (await params).path);
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxy(req, (await params).path);
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxy(req, (await params).path);
}
