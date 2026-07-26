import Link from "next/link";
import { api } from "@/lib/api";
import { dateShort, num, sarCompact } from "@/lib/format";
import Panel from "@/components/Panel";

export default async function MatchmakingPage({
  searchParams,
}: {
  searchParams: Promise<{ min?: string }>;
}) {
  const { min = "50" } = await searchParams; // millions SAR
  const minM = Math.max(0, Number(min) || 50);
  const rows = await api.matchmaking(minM * 1_000_000, 30);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-ink">رادار مقاولي الباطن</h1>
      <p className="text-sm text-ink-2">
        أحدث الفائزين بالعقود الضخمة — هؤلاء سيحتاجون مقاولي باطن وموردين قريبًا. تواصل قبل
        أن يكتمل فريقهم.
      </p>

      <form className="flex items-end gap-2" action="/matchmaking" method="get">
        <label className="text-sm text-ink-2">
          الحد الأدنى لقيمة الترسية (مليون ريال)
          <input
            type="number"
            name="min"
            min={0}
            defaultValue={minM}
            className="mt-1 block w-40 rounded border bg-surface px-3 py-2 text-sm text-ink"
          />
        </label>
        <button type="submit" className="rounded border bg-accent px-4 py-2 text-sm text-white">
          تحديث
        </button>
      </form>

      <Panel title={`ترسيات ≥ ${num(minM)} مليون ريال`} subtitle={`${num(rows.length)} نتيجة — الأحدث موعدًا أولًا`}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[52rem] text-sm">
            <thead>
              <tr className="border-b text-right text-xs text-muted">
                <th className="py-1 font-normal">الفائز</th>
                <th className="py-1 font-normal">المنافسة</th>
                <th className="py-1 font-normal">الجهة</th>
                <th className="py-1 font-normal">القيمة</th>
                <th className="py-1 font-normal">الموعد النهائي</th>
                <th className="py-1 font-normal">المصدر</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.tender_id}-${r.winner_company_id}`} className="border-b border-grid last:border-0">
                  <td className="max-w-[16rem] py-2">
                    {r.winner_company_id ? (
                      <Link href={`/companies/${r.winner_company_id}`} className="text-ink hover:underline">
                        {r.winner}
                      </Link>
                    ) : (
                      <span className="text-ink">{r.winner ?? "غير معروف"}</span>
                    )}
                  </td>
                  <td className="max-w-[18rem] truncate py-2 text-ink-2" title={r.title}>
                    {r.title}
                  </td>
                  <td className="max-w-[12rem] truncate py-2 text-ink-2">{r.agency}</td>
                  <td className="tnum whitespace-nowrap py-2 text-ink-2">{sarCompact(r.award_sar)}</td>
                  <td className="tnum whitespace-nowrap py-2 text-ink-2">{dateShort(r.deadline)}</td>
                  <td className="py-2">
                    {r.details_url ? (
                      <a
                        href={r.details_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-ink-2 underline hover:text-ink"
                      >
                        اعتماد ↗
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
