import Link from "next/link";
import { api } from "@/lib/api";
import { num, pct, sarCompact } from "@/lib/format";
import StatTile from "@/components/StatTile";
import Panel from "@/components/Panel";
import HBar from "@/components/HBar";

export default async function CompanyProfilePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const p = await api.companyProfile(Number(id));
  const maxAgency = Math.max(...p.top_agencies.map((a) => a.total_award_sar ?? 0), 1);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink">{p.name}</h1>
        <p className="mt-1 text-sm text-ink-2">ملف المنافس — الأداء والعملاء الحكوميون</p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatTile label="مرات الفوز" value={num(p.wins)} />
        <StatTile label="عروض مقدمة" value={num(p.bids_participated)} />
        <StatTile
          label="معدل الفوز"
          value={pct(p.win_rate_pct)}
          hint="الفوز ÷ العروض المقدمة"
        />
        <StatTile label="إجمالي الترسيات" value={sarCompact(p.total_award_sar)} hint="ريال سعودي" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="أهم العملاء الحكوميين" subtitle="الجهات التي تفوز لديها هذه الشركة">
          {p.top_agencies.length === 0 ? (
            <p className="text-sm text-muted">لا فوز مسجلًا.</p>
          ) : (
            p.top_agencies.map((a) => (
              <HBar
                key={a.agency_id}
                label={a.agency}
                valueLabel={sarCompact(a.total_award_sar)}
                fraction={(a.total_award_sar ?? 0) / maxAgency}
                href={`/agencies/${a.agency_id}`}
              />
            ))
          )}
        </Panel>

        <Panel title="أنشطة الفوز" subtitle="المجالات التي تتخصص فيها">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-right text-xs text-muted">
                <th className="py-1 font-normal">النشاط</th>
                <th className="py-1 font-normal">مرات الفوز</th>
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

      <Link href="/companies" className="inline-block text-sm text-ink-2 hover:text-ink">
        ← عودة إلى البحث
      </Link>
    </div>
  );
}
