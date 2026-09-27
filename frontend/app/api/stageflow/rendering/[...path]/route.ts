import type { NextRequest } from "next/server";
import { proxy } from "../../../../../src/experience/capability-proxy.server.ts";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "GET", "rendering");
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "POST", "rendering");
}

export async function PUT(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "PUT", "rendering");
}

export async function PATCH(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "PATCH", "rendering");
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "DELETE", "rendering");
}

export async function HEAD(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "HEAD", "rendering");
}

export async function OPTIONS(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "OPTIONS", "rendering");
}
