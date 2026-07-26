import Link from "next/link";
import { api } from "@/lib/api";
import { num, pct, sarCompact } from "@/lib/format";
import StatTile from "@/components/StatTile";
import Panel from "@/components/Panel";
import HBar from "@/components/HBar";

export default async function Dashboard() {
  const [overview, topAgencies, easyMarkets] = await Promise.all([
    api.overview(),
    api.agencies("spend", 8),
    api.competition(200, "least", 5),
  ]);
  const maxSpend = Math.max(...topAgencies.map((a) => a.total_award_sar ?? 0), 1);

  return (
    <div className="space-y-6">
      {/* Hero figure — the one number this dashboard leads with */}
      <section className="rounded-lg border bg-surface p-6">
        <div className="text-sm text-ink-2">إجمالي قيمة الترسيات في المستودع</div>
        <div className="mt-1 text-5xl font-semibold text-ink">
          {sarCompact(overview.total_award_sar)}{" "}
          <span className="text-2xl font-normal text-ink-2">ريال</span>
        </div>
      </section>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label="منافسات مرساة" value={num(overview.tenders)} />
        <StatTile label="شركات فائزة ومشاركة" value={num(overview.companies)} />
        <StatTile label="جهات حكومية" value={num(overview.agencies)} />
        <StatTile
          label="متوسط المنافسين لكل منافسة"
          value={num(overview.avg_bidders, 1)}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel
          title="أكبر الجهات إنفاقًا"
          subtitle="حسب إجمالي قيمة الترسيات — انقر جهة لملفها الكامل"
        >
          {topAgencies.map((a) => (
            <HBar
              key={a.agency_id}
              label={a.agency}
              valueLabel={sarCompact(a.total_award_sar)}
              fraction={(a.total_award_sar ?? 0) / maxSpend}
              href={`/agencies/${a.agency_id}`}
            />
          ))}
          <div className="mt-2 text-left">
            <Link href="/agencies" className="text-xs text-ink-2 hover:text-ink">
              كل الجهات ←
            </Link>
          </div>
        </Panel>

        <Panel
          title="أقل الأسواق ازدحامًا"
          subtitle="أنشطة بأقل متوسط منافسين — فرص دخول أعلى"
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-right text-xs text-muted">
                <th className="py-1 font-normal">النشاط</th>
                <th className="py-1 font-normal">المنافسات</th>
                <th className="py-1 font-normal">متوسط المنافسين</th>
                <th className="py-1 font-normal">عرض وحيد</th>
              </tr>
            </thead>
            <tbody>
              {easyMarkets.map((r) => (
                <tr key={r.activity_id} className="border-b border-grid last:border-0">
                  <td className="max-w-[16rem] truncate py-2 text-ink">{r.activity}</td>
                  <td className="tnum py-2 text-ink-2">{num(r.tenders)}</td>
                  <td className="tnum py-2 text-ink-2">{num(r.avg_bidders, 1)}</td>
                  <td className="tnum py-2 text-ink-2">{pct(r.single_bid_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-2 text-left">
            <Link href="/competition" className="text-xs text-ink-2 hover:text-ink">
              خريطة المنافسة كاملة ←
            </Link>
          </div>
        </Panel>
      </div>
    </div>
  );
}
