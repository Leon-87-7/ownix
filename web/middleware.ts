import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login", "/logout", "/privacy", "/terms", "/restricted"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Mock/demo mode: no real auth backend, so skip the session gate. Guarded to
  // non-production so a stray NEXT_PUBLIC_API_MOCK=1 in a prod build can't ship
  // with auth disabled.
  if (
    process.env.NODE_ENV !== "production" &&
    process.env.NEXT_PUBLIC_API_MOCK === "1"
  ) {
    return NextResponse.next();
  }

  // Public landing stays reachable for everyone (ADR-0035 §1); the CTA is
  // session-aware via the /restricted entry route.
  if (pathname === "/") {
    return NextResponse.next();
  }

  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }

  // The preview cookie grants navigation only — data access is enforced
  // server-side by the /api/preview corpus, and crawler noindex comes from the
  // dashboard layout's robots metadata.
  const session = request.cookies.get("vig_session");
  const preview = request.cookies.get("ownix_preview");
  if (!session?.value && preview?.value !== "1") {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  // Skip _next internals, the API, and any path with a file extension (public/
  // static assets: *.svg, *.png, manifest.json, icon0.svg, …). Without the
  // `.*\.` clause, asset requests made while logged out (i.e. on /login and
  // /logout) hit the session gate and 307 to /login, so the SVGs never load.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/|.*\\.).*)"],
};
