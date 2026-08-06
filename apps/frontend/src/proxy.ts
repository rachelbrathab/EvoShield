import { NextResponse, type NextRequest } from "next/server";

/**
 * Route protection (Next.js 16 "proxy" convention, formerly middleware).
 *
 * The session cookie is httpOnly, so the edge can check only its *presence* —
 * cryptographic validation happens on the backend (every /app API call goes
 * through `get_current_user`). This proxy handles the UX layer: keep
 * unauthenticated visitors out of /app and logged-in users off the auth pages.
 */

const SESSION_COOKIE = "evoshield_session";
const PROTECTED_PREFIX = "/app";

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasSession = request.cookies.has(SESSION_COOKIE);

  // Guard the app: no session → redirect to /login, remembering the target.
  if (pathname.startsWith(PROTECTED_PREFIX) && !hasSession) {
    const loginUrl = new URL("/login", request.url);
    const next = pathname + search;
    if (next !== "/app") loginUrl.searchParams.set("next", next);
    return NextResponse.redirect(loginUrl);
  }

  // Already signed in → skip the auth pages.
  if ((pathname === "/login" || pathname === "/register") && hasSession) {
    const appUrl = new URL("/app", request.url);
    const next = request.nextUrl.searchParams.get("next");
    if (next?.startsWith("/app")) appUrl.pathname = next;
    return NextResponse.redirect(appUrl);
  }

  return NextResponse.next();
}

export const config = {
  // Run on the app routes and auth pages only (not on assets/API calls).
  matcher: ["/app/:path*", "/login", "/register"],
};
