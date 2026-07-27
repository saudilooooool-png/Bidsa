"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

const btn = "rounded border bg-accent px-4 py-2 text-sm text-white disabled:opacity-50";
const input = "rounded border bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted";

export function UpgradeButtons({ plans }: { plans: { key: string; name: string }[] }) {
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function request(plan: string) {
    setBusy(true); setMsg(null);
    try {
      const res = await fetch("/api/proxy/billing/upgrade-request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan }),
      });
      const data = await res.json();
      setMsg(data.message ?? data.detail ?? "تم.");
    } finally { setBusy(false); }
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {plans.map((p) => (
          <button key={p.key} className={btn} disabled={busy} onClick={() => request(p.key)}>
            ترقية إلى {p.name}
          </button>
        ))}
      </div>
      {msg ? <p className="text-sm text-good">{msg}</p> : null}
    </div>
  );
}

export function AddMemberForm() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <form
      className="flex flex-wrap items-end gap-2"
      onSubmit={async (e) => {
        e.preventDefault();
        const form = e.currentTarget;
        const f = new FormData(form);
        setBusy(true); setError(null);
        try {
          const res = await fetch("/api/proxy/team/members", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: String(f.get("email")),
              full_name: String(f.get("full_name")),
              password: String(f.get("password")),
              role: String(f.get("role")),
            }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) {
            setError(typeof data.detail === "string" ? data.detail : "تعذر إضافة العضو.");
            return;
          }
          form.reset();
          router.refresh();
        } finally { setBusy(false); }
      }}
    >
      <input className={input} name="full_name" placeholder="الاسم" required minLength={2} />
      <input className={input} name="email" type="email" placeholder="البريد" required dir="ltr" />
      <input className={input} name="password" type="password" placeholder="كلمة مرور مؤقتة" required minLength={8} dir="ltr" />
      <select className={input} name="role" defaultValue="member">
        <option value="member">عضو</option>
        <option value="admin">مشرف</option>
      </select>
      <button className={btn} disabled={busy}>{busy ? "..." : "إضافة"}</button>
      {error ? <p className="w-full text-sm text-critical">{error}</p> : null}
    </form>
  );
}

export function LogoutButton() {
  const router = useRouter();
  return (
    <button
      className="rounded border px-3 py-1 text-sm text-ink-2 hover:text-ink"
      onClick={async () => {
        await fetch("/api/auth/logout", { method: "POST" });
        router.push("/");
        router.refresh();
      }}
    >
      تسجيل الخروج
    </button>
  );
}
