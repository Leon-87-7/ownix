import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/login", "/logout"];

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

  if (
    PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))
  ) {
    return NextResponse.next();
  }

  const session = request.cookies.get("vig_session");
  if (!session?.value) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/).*)"],
};
