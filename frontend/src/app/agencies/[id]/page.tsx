import Link from "next/link";
import { IS_DEMO, api } from "@/lib/api";
import { num, pct, sarCompact } from "@/lib/format";
import StatTile from "@/components/StatTile";
import Panel from "@/components/Panel";
import HBar from "@/components/HBar";
import Meter from "@/components/Meter";

export default async function AgencyProfilePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const p = await api.agencyProfile(Number(id));
  if (!p) {
    return (
      <div className="rounded-lg border bg-surface p-8 text-center">
        <h1 className="text-lg font-bold text-ink">الملف غير متاح</h1>
        <p className="mt-2 text-sm text-ink-2">
          {IS_DEMO
            ? "النسخة التجريبية تتضمن ملفات أكبر 24 جهة فقط — اربط الخادم الخلفي لعرض كل الجهات."
            : "لم يتم العثور على هذه الجهة."}
        </p>
        <Link href="/agencies" className="mt-4 inline-block text-sm text-accent hover:underline">
          ← عودة إلى الجهات
        </Link>
      </div>
    );
  }
  const maxWinner = Math.max(...p.top_winners.map((w) => w.total_award_sar ?? 0), 1);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink">{p.agency}</h1>
        <p className="mt-1 text-sm text-ink-2">ملف المشتري — سلوك الترسية والموردون المهيمنون</p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label="منافسات مرساة" value={num(p.tenders)} />
        <StatTile label="إجمالي الترسيات" value={sarCompact(p.total_award_sar)} hint="ريال سعودي" />
        <StatTile label="متوسط المنافسين" value={num(p.avg_bidders, 1)} />
        <div className="rounded-lg border bg-surface p-4">
          <div className="text-sm text-ink-2">منافسات بعرض وحيد</div>
          <div className="mt-2">
            <Meter pct={p.single_bid_pct} label={pct(p.single_bid_pct)} />
          </div>
          <div className="mt-1 text-xs text-muted">مؤشر ضعف المزاحمة لدى الجهة</div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel
          title="الموردون المهيمنون"
          subtitle="أكبر 10 فائزين لدى الجهة وحصتهم من قيمة ترسياتها"
        >
          {p.top_winners.map((w) => (
            <div key={`${w.company_id}-${w.company}`}>
              <HBar
                label={w.company ?? "غير معروف"}
                valueLabel={`${sarCompact(w.total_award_sar)} · ${pct(w.share_pct)}`}
                fraction={(w.total_award_sar ?? 0) / maxWinner}
                href={w.company_id ? `/companies/${w.company_id}` : undefined}
              />
            </div>
          ))}
        </Panel>

        <Panel title="أهم الأنشطة" subtitle="أين تُنفق هذه الجهة أموالها">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-right text-xs text-muted">
                <th className="py-1 font-normal">النشاط</th>
                <th className="py-1 font-normal">المنافسات</th>
                <th className="py-1 font-normal">القيمة</th>
              </tr>
            </thead>
            <tbody>
              {p.top_activities.map((a) => (
                <tr key={`${a.activity_id}`} className="border-b border-grid last:border-0">
                  <td className="max-w-[16rem] truncate py-2 text-ink">{a.activity}</td>
                  <td className="tnum py-2 text-ink-2">{num(a.tenders)}</td>
                  <td className="tnum py-2 text-ink-2">{sarCompact(a.total_award_sar)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>

      <Link href="/agencies" className="inline-block text-sm text-ink-2 hover:text-ink">
        ← عودة إلى الجهات
      </Link>
    </div>
  );
}
