import { NextRequest, NextResponse } from "next/server";

const PROTECTED = ["/matching", "/proposals", "/settings"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PROTECTED.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    if (!request.cookies.get("bidsa_token")?.value) {
      const url = request.nextUrl.clone();
      url.pathname = "/login";
      url.searchParams.set("next", pathname);
      return NextResponse.redirect(url);
    }
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/matching/:path*", "/proposals/:path*", "/settings/:path*"],
};
