import { NextResponse } from "next/server";
import { TOKEN_COOKIE } from "@/lib/session";

const API_URL = process.env.API_URL;

/** Call a backend auth endpoint and turn its token into an httpOnly cookie. */
export async function establishSession(path: string, body: unknown) {
  if (!API_URL) {
    return NextResponse.json(
      { detail: "الوضع التجريبي لا يدعم الحسابات — الخادم الخلفي غير مربوط." },
      { status: 503 },
    );
  }
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return NextResponse.json(data, { status: res.status });
  }
  const out = NextResponse.json({
    ok: true,
    company: data.company,
    subscription: data.subscription,
  });
  out.cookies.set(TOKEN_COOKIE, data.token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 7 * 24 * 3600,
  });
  return out;
}
