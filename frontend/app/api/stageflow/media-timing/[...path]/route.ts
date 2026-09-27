import type { NextRequest } from "next/server";
import { proxy } from "../../../../../src/experience/capability-proxy.server.ts";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "GET", "media-timing");
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "POST", "media-timing");
}

export async function PUT(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "PUT", "media-timing");
}

export async function PATCH(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "PATCH", "media-timing");
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "DELETE", "media-timing");
}

export async function HEAD(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "HEAD", "media-timing");
}

export async function OPTIONS(request: NextRequest, context: { params: Promise<{ path: string[] }> }): Promise<Response> {
  return proxy(request, (await context.params).path, "OPTIONS", "media-timing");
}
