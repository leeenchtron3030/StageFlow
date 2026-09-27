import type { NextRequest } from "next/server";
import { proxy } from "../../../../../src/experience/capability-proxy.server.ts";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "GET", "editorial");
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "POST", "editorial");
}

export async function PUT(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "PUT", "editorial");
}

export async function PATCH(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "PATCH", "editorial");
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "DELETE", "editorial");
}

export async function HEAD(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "HEAD", "editorial");
}

export async function OPTIONS(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "OPTIONS", "editorial");
}
