import type { NextRequest } from "next/server";
import { proxy } from "../../../../../src/experience/capability-proxy.server.ts";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "GET", "demo");
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "POST", "demo");
}
