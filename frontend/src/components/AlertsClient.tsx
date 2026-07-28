"use client";

import Link from "next/link";
import { useState } from "react";
import type { Alert } from "@/app/alerts/page";
import type { FeedItem, LookupItem } from "@/lib/api";

const btn = "rounded border bg-accent px-4 py-2 text-sm text-white disabled:opacity-50";

export default function AlertsClient({
  initial,
  activities,
  regions,
  loggedIn,
}: {
  initial: Alert[];
  activities: LookupItem[];
  regions: LookupItem[];
  loggedIn: boolean;
}) {
  const [alerts, setAlerts] = useState<Alert[]>(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ id: string; items: FeedItem[] } | null>(null);

  const activityName = (id: number | null) =>
    id == null ? null : activities.find((a) => a.id === id)?.name ?? `#${id}`;
  const regionName = (id: number | null) =>
    id == null ? null : regions.find((r) => r.id === id)?.name ?? `#${id}`;

  async function proxy(path: string, init?: RequestInit) {
    const res = await fetch(`/api/proxy/${path}`, init);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "خطأ غير متوقع");
    return data;
  }

  async function create(form: HTMLFormElement) {
    const fd = new FormData(form);
    const name = String(fd.get("name") ?? "").trim();
    if (!name) return;
    const body = {
      name,
      keywords: String(fd.get("keywords") ?? "").trim() || null,
      activity_id: fd.get("activity_id") ? Number(fd.get("activity_id")) : null,
      region_id: fd.get("region_id") ? Number(fd.get("region_id")) : null,
      notify_email: fd.get("notify_email") === "on",
    };
    setBusy("create"); setError(null);
    try {
      const created = (await proxy("alerts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })) as Alert;
      setAlerts((a) => [created, ...a]);
      form.reset();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(null); }
  }

  async function remove(id: string) {
    setBusy(id); setError(null);
    try {
      await proxy(`alerts/${id}`, { method: "DELETE" });
      setAlerts((a) => a.filter((x) => x.id !== id));
      if (preview?.id === id) setPreview(null);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(null); }
  }

  async function runPreview(id: string) {
    setBusy(`p-${id}`); setError(null);
    try {
      const data = await proxy(`alerts/${id}/preview`, { method: "GET" });
      setPreview({ id, items: (data.matches ?? []) as FeedItem[] });
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(null); }
  }

  if (!loggedIn) {
    return (
      <div className="rounded-lg border bg-surface p-6 text-sm text-ink-2">
        تنبيهات المنافسات ميزة للمشتركين.{" "}
        <Link href="/login" className="text-accent hover:underline">سجّل الدخول</Link>{" "}
        أو{" "}
        <Link href="/register" className="text-accent hover:underline">ابدأ تجربة مجانية</Link>{" "}
        لإنشاء تنبيهاتك، ثم تصلك المنافسات الجديدة المطابقة على بريدك.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-lg border bg-surface p-4">
        <h2 className="text-base font-semibold text-ink">تنبيه جديد</h2>
        <p className="mt-0.5 text-xs text-muted">
          حدّد الكلمات والنشاط والمنطقة — كل المعايير اختيارية، والفارغ يعني «الكل».
        </p>
        <form
          className="mt-3 grid gap-3 sm:grid-cols-2"
          onSubmit={(e) => { e.preventDefault(); create(e.currentTarget); }}
        >
          <input
            name="name" required maxLength={120} placeholder="اسم التنبيه (مثال: مشاريع تقنية بالرياض)"
            className="rounded border bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted sm:col-span-2"
          />
          <input
            name="keywords" placeholder="كلمات مفتاحية (مثال: أمن سيبراني، شبكات)"
            className="rounded border bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted sm:col-span-2"
          />
          <select name="activity_id" defaultValue=""
            className="rounded border bg-surface px-2 py-2 text-sm text-ink">
            <option value="">كل الأنشطة</option>
            {activities.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <select name="region_id" defaultValue=""
            className="rounded border bg-surface px-2 py-2 text-sm text-ink">
            <option value="">كل المناطق</option>
            {regions.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
          <label className="flex items-center gap-2 text-sm text-ink-2">
            <input type="checkbox" name="notify_email" defaultChecked />
            أرسل تنبيهًا بالبريد عند المطابقات الجديدة
          </label>
          <div className="sm:col-span-2">
            <button className={btn} disabled={busy === "create"}>
              {busy === "create" ? "جارٍ الحفظ…" : "حفظ التنبيه"}
            </button>
          </div>
        </form>
      </section>

      <section className="rounded-lg border bg-surface p-4">
        <h2 className="text-base font-semibold text-ink">تنبيهاتي</h2>
        {alerts.length === 0 ? (
          <p className="mt-3 text-sm text-muted">لا تنبيهات بعد — أنشئ أول تنبيه أعلاه.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {alerts.map((a) => (
              <li key={a.id} className="rounded border border-grid p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-medium text-ink">{a.name}</p>
                    <p className="mt-0.5 text-xs text-muted">
                      {[
                        a.keywords ? `«${a.keywords}»` : null,
                        activityName(a.activity_id),
                        regionName(a.region_id),
                        a.notify_email ? "بريد ✓" : "بدون بريد",
                      ].filter(Boolean).join(" · ") || "كل المنافسات المفتوحة"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      className="rounded border px-3 py-1 text-xs text-ink-2 hover:text-ink disabled:opacity-50"
                      onClick={() => runPreview(a.id)} disabled={busy === `p-${a.id}`}
                    >
                      {busy === `p-${a.id}` ? "..." : "المطابقات الآن"}
                    </button>
                    <button
                      className="rounded border px-3 py-1 text-xs text-critical hover:opacity-80 disabled:opacity-50"
                      onClick={() => remove(a.id)} disabled={busy === a.id}
                    >
                      {busy === a.id ? "..." : "حذف"}
                    </button>
                  </div>
                </div>

                {preview?.id === a.id ? (
                  <div className="mt-3 border-t border-grid pt-3">
                    {preview.items.length === 0 ? (
                      <p className="text-xs text-muted">لا منافسات مفتوحة مطابقة الآن.</p>
                    ) : (
                      <ul className="space-y-1 text-sm">
                        {preview.items.map((m) => (
                          <li key={m.tender_id} className="flex items-start justify-between gap-3">
                            <span className="line-clamp-1 text-ink-2" title={m.title}>
                              {m.details_url ? (
                                <a href={m.details_url} target="_blank" rel="noopener noreferrer"
                                  className="hover:text-ink hover:underline">{m.title}</a>
                              ) : m.title}
                            </span>
                            {m.days_left != null ? (
                              <span className="shrink-0 text-xs text-muted">{m.days_left} يومًا</span>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      {error ? <p className="text-sm text-critical">{error}</p> : null}
    </div>
  );
}
