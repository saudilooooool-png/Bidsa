"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

function useSubmit(endpoint: string) {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(body: Record<string, string>) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(typeof data.detail === "string" ? data.detail : "حدث خطأ — تحقق من البيانات.");
        return;
      }
      router.push(params.get("next") ?? "/matching");
      router.refresh();
    } finally {
      setBusy(false);
    }
  }
  return { submit, error, busy };
}

const input =
  "w-full rounded border bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted";
const button =
  "w-full rounded border bg-accent px-4 py-2 text-sm text-white disabled:opacity-50";

function LoginInner() {
  const { submit, error, busy } = useSubmit("/api/auth/login");
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        submit({ email: String(f.get("email")), password: String(f.get("password")) });
      }}
    >
      <input className={input} name="email" type="email" placeholder="البريد الإلكتروني" required dir="ltr" />
      <input className={input} name="password" type="password" placeholder="كلمة المرور" required dir="ltr" />
      {error ? <p className="text-sm text-critical">{error}</p> : null}
      <button className={button} disabled={busy}>{busy ? "..." : "تسجيل الدخول"}</button>
    </form>
  );
}

function RegisterInner() {
  const { submit, error, busy } = useSubmit("/api/auth/register");
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        submit({
          company_name: String(f.get("company_name")),
          full_name: String(f.get("full_name")),
          email: String(f.get("email")),
          password: String(f.get("password")),
        });
      }}
    >
      <input className={input} name="company_name" placeholder="اسم الشركة" required minLength={2} />
      <input className={input} name="full_name" placeholder="اسمك الكامل" required minLength={2} />
      <input className={input} name="email" type="email" placeholder="البريد الإلكتروني" required dir="ltr" />
      <input
        className={input} name="password" type="password"
        placeholder="كلمة المرور (8 أحرف فأكثر)" required minLength={8} dir="ltr"
      />
      {error ? <p className="text-sm text-critical">{error}</p> : null}
      <button className={button} disabled={busy}>
        {busy ? "..." : "ابدأ تجربتك المجانية — 14 يومًا"}
      </button>
    </form>
  );
}

export function LoginForm() {
  return <Suspense><LoginInner /></Suspense>;
}

export function RegisterForm() {
  return <Suspense><RegisterInner /></Suspense>;
}
