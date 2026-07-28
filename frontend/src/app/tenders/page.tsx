import Link from "next/link";
import { api, IS_DEMO } from "@/lib/api";
import { num, dateShort } from "@/lib/format";
import Panel from "@/components/Panel";

export const dynamic = "force-dynamic";

export default async function TendersFeedPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; activity_id?: string; region_id?: string; within?: string; page?: string }>;
}) {
  const sp = await searchParams;
  const lookups = await api.lookups();
  const params = new URLSearchParams();
  if (sp.q) params.set("search", sp.q);
  if (sp.activity_id) params.set("activity_id", sp.activity_id);
  if (sp.region_id) params.set("region_id", sp.region_id);
  if (sp.within) params.set("within_days", sp.within);
  const page = Math.max(1, Number(sp.page) || 1);
  params.set("page", String(page));
  params.set("page_size", "25");
  const feed = await api.feed(params);
  const pages = Math.max(1, Math.ceil(feed.total / feed.page_size));

  function pageHref(p: number) {
    const u = new URLSearchParams();
    if (sp.q) u.set("q", sp.q);
    if (sp.activity_id) u.set("activity_id", sp.activity_id);
    if (sp.region_id) u.set("region_id", sp.region_id);
    if (sp.within) u.set("within", sp.within);
    u.set("page", String(p));
    return `/tenders?${u.toString()}`;
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-ink">المنافسات المفتوحة</h1>
        <p className="mt-1 text-sm text-ink-2">
          كل المنافسات التي لم ينتهِ موعدها بعد — فلتر بالنشاط والمنطقة وقرب الموعد.
        </p>
      </div>

      {IS_DEMO ? (
        <div className="rounded-lg border bg-surface p-4 text-sm text-ink-2">
          النسخة التجريبية تعرض المستودع التاريخي فقط. المنافسات المفتوحة الحية تظهر هنا عند ربط
          الخادم وتشغيل الجلب.
        </div>
      ) : null}

      <form className="flex flex-wrap items-end gap-3" action="/tenders" method="get">
        <input
          name="q" defaultValue={sp.q ?? ""} placeholder="بحث في العنوان…"
          className="w-56 rounded border bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted"
        />
        <select name="activity_id" defaultValue={sp.activity_id ?? ""}
          className="w-56 rounded border bg-surface px-2 py-2 text-sm text-ink">
          <option value="">كل الأنشطة</option>
          {lookups.activities.slice(0, 60).map((a) => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
        <select name="region_id" defaultValue={sp.region_id ?? ""}
          className="w-44 rounded border bg-surface px-2 py-2 text-sm text-ink">
          <option value="">كل المناطق</option>
          {lookups.regions.slice(0, 30).map((r) => (
            <option key={r.id} value={r.id}>{r.name}</option>
          ))}
        </select>
        <select name="within" defaultValue={sp.within ?? ""}
          className="w-40 rounded border bg-surface px-2 py-2 text-sm text-ink">
          <option value="">أي موعد</option>
          <option value="7">تنتهي خلال 7 أيام</option>
          <option value="14">تنتهي خلال 14 يومًا</option>
          <option value="30">تنتهي خلال 30 يومًا</option>
        </select>
        <button className="rounded border bg-accent px-4 py-2 text-sm text-white">تصفية</button>
      </form>

      <Panel title={`${num(feed.total)} منافسة مفتوحة`} subtitle="مرتّبة بالأقرب موعدًا">
        {feed.items.length === 0 ? (
          <p className="text-sm text-muted">لا منافسات مفتوحة مطابقة حاليًا.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[48rem] text-sm">
              <thead>
                <tr className="border-b text-right text-xs text-muted">
                  <th className="py-1 font-normal">المنافسة</th>
                  <th className="py-1 font-normal">الجهة</th>
                  <th className="py-1 font-normal">النشاط</th>
                  <th className="py-1 font-normal">الموعد</th>
                  <th className="py-1 font-normal">المتبقّي</th>
                  <th className="py-1 font-normal">المصدر</th>
                </tr>
              </thead>
              <tbody>
                {feed.items.map((t) => (
                  <tr key={t.tender_id} className="border-b border-grid last:border-0">
                    <td className="max-w-[22rem] py-2 text-ink" title={t.title}>
                      <span className="line-clamp-2">{t.title}</span>
                      <span className="block text-xs text-muted" dir="ltr">{t.reference_number}</span>
                    </td>
                    <td className="max-w-[10rem] truncate py-2 text-ink-2">{t.agency ?? "—"}</td>
                    <td className="max-w-[10rem] truncate py-2 text-ink-2">{t.activity ?? "—"}</td>
                    <td className="tnum whitespace-nowrap py-2 text-ink-2">{dateShort(t.deadline)}</td>
                    <td className="py-2">
                      {t.days_left != null ? (
                        <span className={`rounded px-2 py-0.5 text-xs ${t.days_left <= 3 ? "bg-[color:var(--status-critical)] text-white" : "text-ink-2"}`}>
                          {num(t.days_left)} يومًا
                        </span>
                      ) : "—"}
                    </td>
                    <td className="py-2">
                      {t.details_url ? (
                        <a href={t.details_url} target="_blank" rel="noopener noreferrer"
                          className="text-xs text-ink-2 underline hover:text-ink">اعتماد ↗</a>
                      ) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {pages > 1 ? (
          <div className="mt-4 flex items-center justify-center gap-3 text-sm">
            {page > 1 ? <Link href={pageHref(page - 1)} className="text-ink-2 hover:text-ink">→ السابق</Link> : null}
            <span className="text-muted">صفحة {num(page)} من {num(pages)}</span>
            {page < pages ? <Link href={pageHref(page + 1)} className="text-ink-2 hover:text-ink">التالي ←</Link> : null}
          </div>
        ) : null}
      </Panel>
    </div>
  );
}
