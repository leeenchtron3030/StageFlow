import { NextResponse, type NextRequest } from "next/server.js";
import { isAllowedUiHost } from "./src/experience/ui-host-policy.server.ts";

export function proxy(request: NextRequest) {
  // next dev/start set PORT from server.address().port before handling requests.
  // Node runtime keeps this a runtime read, including CLI ports and dev fallback.
  if (!isAllowedUiHost(request.headers.get("host"), process.env.PORT, process.env.STAGEFLOW_UI_ALLOWED_HOSTS)) {
    return new NextResponse(null, { status: 421, headers: { "Cache-Control": "no-store" } });
  }
  return NextResponse.next();
}

// No asset/API exclusions, method filters, or prefetch bypasses.
export const config = { matcher: "/:path*" };
