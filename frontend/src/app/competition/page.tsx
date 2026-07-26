import Link from "next/link";
import { api } from "@/lib/api";
import { num, pct, sarCompact } from "@/lib/format";
import Panel from "@/components/Panel";
import Meter from "@/components/Meter";

export default async function CompetitionPage({
  searchParams,
}: {
  searchParams: Promise<{ order?: string }>;
}) {
  const { order = "least" } = await searchParams;
  const rows = await api.competition(100, order, 30);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-ink">خريطة المنافسة</h1>
      <p className="text-sm text-ink-2">
        أين تشتد المزاحمة وأين تنعدم؟ نسبة «العرض الوحيد» العالية تعني سوقًا يفوز فيه من يتقدم أصلًا.
      </p>
      <div className="flex gap-2 text-sm">
        <Link
          href="/competition?order=least"
          className={`rounded border px-3 py-1 ${order === "least" ? "bg-accent text-white" : "bg-surface text-ink-2 hover:text-ink"}`}
        >
          الأقل ازدحامًا أولًا
        </Link>
        <Link
          href="/competition?order=most"
          className={`rounded border px-3 py-1 ${order === "most" ? "bg-accent text-white" : "bg-surface text-ink-2 hover:text-ink"}`}
        >
          الأشد ازدحامًا أولًا
        </Link>
      </div>

      <Panel title="الأنشطة (100 منافسة فأكثر)" subtitle="متوسط المنافسين ونسبة العرض الوحيد ووسيط قيمة العقد">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-right text-xs text-muted">
              <th className="py-1 font-normal">النشاط</th>
              <th className="py-1 font-normal">المنافسات</th>
              <th className="py-1 font-normal">متوسط المنافسين</th>
              <th className="py-1 font-normal">عرض وحيد</th>
              <th className="py-1 font-normal">وسيط العقد</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.activity_id} className="border-b border-grid last:border-0">
                <td className="max-w-[20rem] truncate py-2 text-ink">{r.activity}</td>
                <td className="tnum py-2 text-ink-2">{num(r.tenders)}</td>
                <td className="tnum py-2 text-ink-2">{num(r.avg_bidders, 1)}</td>
                <td className="py-2">
                  <Meter pct={r.single_bid_pct} label={pct(r.single_bid_pct)} />
                </td>
                <td className="tnum py-2 text-ink-2">{sarCompact(r.median_award_sar)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
