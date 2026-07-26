import Link from "next/link";
import { api } from "@/lib/api";
import { num, sarCompact } from "@/lib/format";
import Panel from "@/components/Panel";

const SORTS = [
  { key: "spend", label: "الإنفاق" },
  { key: "tenders", label: "عدد المنافسات" },
  { key: "competition", label: "شدة المنافسة" },
];

export default async function AgenciesPage({
  searchParams,
}: {
  searchParams: Promise<{ sort?: string }>;
}) {
  const { sort = "spend" } = await searchParams;
  const rows = await api.agencies(sort, 50);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-ink">الجهات الحكومية</h1>
      <div className="flex gap-2 text-sm">
        {SORTS.map((s) => (
          <Link
            key={s.key}
            href={`/agencies?sort=${s.key}`}
            className={`rounded border px-3 py-1 ${
              sort === s.key ? "bg-accent text-white" : "bg-surface text-ink-2 hover:text-ink"
            }`}
          >
            {s.label}
          </Link>
        ))}
      </div>
      <Panel title={`أعلى ${rows.length} جهة`} subtitle="انقر جهة لعرض ملفها الكامل">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-right text-xs text-muted">
              <th className="py-1 font-normal">الجهة</th>
              <th className="py-1 font-normal">المنافسات</th>
              <th className="py-1 font-normal">إجمالي الترسيات</th>
              <th className="py-1 font-normal">متوسط المنافسين</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.agency_id} className="border-b border-grid last:border-0">
                <td className="max-w-[24rem] py-2">
                  <Link href={`/agencies/${a.agency_id}`} className="text-ink hover:underline">
                    {a.agency}
                  </Link>
                </td>
                <td className="tnum py-2 text-ink-2">{num(a.tenders)}</td>
                <td className="tnum py-2 text-ink-2">{sarCompact(a.total_award_sar)}</td>
                <td className="tnum py-2 text-ink-2">{num(a.avg_bidders, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
