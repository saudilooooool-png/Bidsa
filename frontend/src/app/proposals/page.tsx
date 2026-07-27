import Link from "next/link";
import { authFetch } from "@/lib/session";
import { dateShort } from "@/lib/format";
import Panel from "@/components/Panel";

interface ProposalRow {
  id: string; status: string; tender_title: string;
  reference_number: string; model: string | null; created_at: string;
}

export default async function ProposalsPage() {
  const rows = (await authFetch<ProposalRow[]>("/api/v1/proposals")) ?? [];
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-ink">مسودات العروض الفنية</h1>
      <Panel title={`${rows.length} مسودة`} subtitle="كل مسودة مرتبطة بمنافسة من المستودع">
        {rows.length === 0 ? (
          <p className="text-sm text-muted">
            لا مسودات بعد —{" "}
            <Link href="/matching" className="text-accent hover:underline">
              شغّل المطابقة وولّد أول مسودة
            </Link>.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-right text-xs text-muted">
                <th className="py-1 font-normal">المنافسة</th>
                <th className="py-1 font-normal">الحالة</th>
                <th className="py-1 font-normal">التاريخ</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((p) => (
                <tr key={p.id} className="border-b border-grid last:border-0">
                  <td className="max-w-[26rem] py-2">
                    <Link href={`/proposals/${p.id}`} className="text-ink hover:underline">
                      {p.tender_title}
                    </Link>
                    <div className="text-xs text-muted" dir="ltr">{p.reference_number}</div>
                  </td>
                  <td className="py-2 text-ink-2">{p.status === "draft" ? "مسودة" : p.status}</td>
                  <td className="tnum whitespace-nowrap py-2 text-ink-2">{dateShort(p.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
