import type { NextRequest } from "next/server";
import { proxy } from "../../../../../src/experience/capability-proxy.server.ts";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "GET", "session-suggestions");
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "POST", "session-suggestions");
}

export async function PUT(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "PUT", "session-suggestions");
}

export async function PATCH(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "PATCH", "session-suggestions");
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "DELETE", "session-suggestions");
}

export async function HEAD(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "HEAD", "session-suggestions");
}

export async function OPTIONS(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "OPTIONS", "session-suggestions");
}
