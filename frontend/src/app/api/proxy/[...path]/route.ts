import { NextRequest, NextResponse } from "next/server";
import { TOKEN_COOKIE } from "@/lib/session";

const API_URL = process.env.API_URL;

// Only SaaS mutation endpoints may pass through — never an open proxy.
const ALLOWED_PREFIXES = [
  "team/members",
  "knowledge/upload",
  "knowledge/match",
  "knowledge/documents",
  "proposals/generate",
  "billing/upgrade-request",
];

async function forward(req: NextRequest, pathParts: string[], method: string) {
  const path = pathParts.join("/");
  if (!ALLOWED_PREFIXES.some((p) => path === p || path.startsWith(`${p}/`))) {
    return NextResponse.json({ detail: "path not allowed" }, { status: 403 });
  }
  if (!API_URL) {
    return NextResponse.json(
      { detail: "الوضع التجريبي — الخادم الخلفي غير مربوط." }, { status: 503 });
  }
  const token = req.cookies.get(TOKEN_COOKIE)?.value;
  if (!token) {
    return NextResponse.json({ detail: "غير مسجل الدخول" }, { status: 401 });
  }
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const contentType = req.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;

  // Buffering keeps multipart bodies (with their boundary header) intact.
  const body = method === "DELETE" ? undefined : Buffer.from(await req.arrayBuffer());
  const res = await fetch(`${API_URL}/api/v1/${path}`, {
    method, headers, body, cache: "no-store",
  });
  const data = await res.json().catch(() => ({}));
  return NextResponse.json(data, { status: res.status });
}

export async function POST(
  req: NextRequest, ctx: { params: Promise<{ path: string[] }> },
) {
  const { path } = await ctx.params;
  return forward(req, path, "POST");
}

export async function DELETE(
  req: NextRequest, ctx: { params: Promise<{ path: string[] }> },
) {
  const { path } = await ctx.params;
  return forward(req, path, "DELETE");
}
