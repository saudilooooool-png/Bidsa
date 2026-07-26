import { api } from "@/lib/api";
import { num, sarCompact } from "@/lib/format";
import StatTile from "@/components/StatTile";
import Panel from "@/components/Panel";

export default async function PricingPage({
  searchParams,
}: {
  searchParams: Promise<{ activity_id?: string; region_id?: string; q?: string }>;
}) {
  const sp = await searchParams;
  const lookups = await api.lookups();

  const params = new URLSearchParams();
  if (sp.activity_id) params.set("activity_id", sp.activity_id);
  if (sp.region_id) params.set("region_id", sp.region_id);
  if (sp.q) params.set("activity_contains", sp.q);
  const hasFilter = [...params.keys()].length > 0;
  const bench = await api.pricing(params);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-ink">التسعير المعياري</h1>
      <p className="text-sm text-ink-2">
        كم رست العقود المشابهة فعليًا؟ فلتر بالنشاط والمنطقة لتحصل على المتوسط والوسيط والمدى
        الربيعي — مرجعك قبل بناء أي عرض سعر.
      </p>

      <form className="flex flex-wrap items-end gap-3" action="/pricing" method="get">
        <label className="text-sm text-ink-2">
          النشاط
          <select
            name="activity_id"
            defaultValue={sp.activity_id ?? ""}
            className="mt-1 block w-64 rounded border bg-surface px-2 py-2 text-sm text-ink"
          >
            <option value="">كل الأنشطة</option>
            {lookups.activities.slice(0, 60).map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} ({num(a.tenders)})
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-ink-2">
          المنطقة
          <select
            name="region_id"
            defaultValue={sp.region_id ?? ""}
            className="mt-1 block w-52 rounded border bg-surface px-2 py-2 text-sm text-ink"
          >
            <option value="">كل المناطق</option>
            {lookups.regions.slice(0, 30).map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} ({num(r.tenders)})
              </option>
            ))}
          </select>
        </label>
        <button type="submit" className="rounded border bg-accent px-4 py-2 text-sm text-white">
          احسب المعيار
        </button>
      </form>

      <Panel
        title={hasFilter ? "معيار الشريحة المحددة" : "معيار السوق كاملًا"}
        subtitle={`${num(bench.contracts)} عقدًا مرساة في هذه الشريحة`}
      >
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatTile label="الوسيط (الأدق للتسعير)" value={sarCompact(bench.median_sar)} hint="ريال" />
          <StatTile label="المتوسط" value={sarCompact(bench.avg_sar)} hint="يتأثر بالعقود العملاقة" />
          <StatTile
            label="المدى الربيعي"
            value={`${sarCompact((bench.p25_halalas ?? 0) / 100)} – ${sarCompact((bench.p75_halalas ?? 0) / 100)}`}
            hint="٥٠٪ من العقود داخل هذا المدى"
          />
          <StatTile label="متوسط المنافسين" value={num(bench.avg_bidders, 1)} />
        </div>
        <p className="mt-3 text-xs text-muted">
          المدى الكامل: {sarCompact((bench.min_halalas ?? 0) / 100)} إلى{" "}
          {sarCompact((bench.max_halalas ?? 0) / 100)} ريال.
        </p>
      </Panel>
    </div>
  );
}
