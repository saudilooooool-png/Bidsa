import { cookies } from "next/headers";

export const TOKEN_COOKIE = "bidsa_token";

const API_URL = process.env.API_URL;

export async function getToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(TOKEN_COOKIE)?.value ?? null;
}

/** Server-side fetch to the backend with the session token attached. */
export async function authFetch<T>(path: string): Promise<T | null> {
  if (!API_URL) return null; // demo mode: SaaS features need the live backend
  const token = await getToken();
  if (!token) return null;
  const res = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 401 || res.status === 402) return null;
  if (!res.ok) throw new Error(`API ${res.status} on ${path}`);
  return res.json() as Promise<T>;
}

export interface Me {
  email: string;
  full_name: string | null;
  role: string;
  company: string;
  subscription: { state: string; plan: string; trial_days_left: number | null };
}

export async function currentUser(): Promise<Me | null> {
  try {
    return await authFetch<Me>("/api/v1/auth/me");
  } catch {
    return null;
  }
}
