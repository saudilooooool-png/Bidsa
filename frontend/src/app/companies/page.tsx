import Link from "next/link";
import { api } from "@/lib/api";
import { num, sarCompact } from "@/lib/format";
import Panel from "@/components/Panel";

export default async function CompaniesPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q = "" } = await searchParams;
  const rows = q.length >= 2 ? await api.searchCompanies(q, 30) : [];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-ink">الشركات</h1>
      <form className="flex gap-2" action="/companies" method="get">
        <input
          type="text"
          name="q"
          defaultValue={q}
          placeholder="ابحث باسم الشركة (حرفان على الأقل)…"
          className="w-full max-w-md rounded border bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted"
        />
        <button
          type="submit"
          className="rounded border bg-accent px-4 py-2 text-sm text-white"
        >
          بحث
        </button>
      </form>

      {q.length >= 2 ? (
        <Panel title={`نتائج البحث عن «${q}»`} subtitle={`${num(rows.length)} شركة`}>
          {rows.length === 0 ? (
            <p className="text-sm text-muted">لا نتائج.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-right text-xs text-muted">
                  <th className="py-1 font-normal">الشركة</th>
                  <th className="py-1 font-normal">مرات الفوز</th>
                  <th className="py-1 font-normal">إجمالي الترسيات</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.company_id} className="border-b border-grid last:border-0">
                    <td className="max-w-[24rem] py-2">
                      <Link
                        href={`/companies/${c.company_id}`}
                        className="text-ink hover:underline"
                      >
                        {c.name}
                      </Link>
                    </td>
                    <td className="tnum py-2 text-ink-2">{num(c.wins)}</td>
                    <td className="tnum py-2 text-ink-2">{sarCompact(c.total_award_sar)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      ) : (
        <p className="text-sm text-muted">
          ابحث عن أي شركة لعرض ملفها: مرات الفوز، معدل الفوز، وأهم عملائها الحكوميين.
        </p>
      )}
    </div>
  );
}
