import Link from "next/link";
import { authFetch } from "@/lib/session";

interface ProposalDetail {
  id: string; status: string; tender_title: string;
  reference_number: string; model: string | null;
  content: string; created_at: string;
}

export default async function ProposalDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const p = await authFetch<ProposalDetail>(`/api/v1/proposals/${id}`);
  if (!p) {
    return (
      <div className="rounded-lg border bg-surface p-8 text-center">
        <p className="text-sm text-ink-2">المسودة غير موجودة أو انتهت جلستك.</p>
        <Link href="/proposals" className="mt-3 inline-block text-sm text-accent hover:underline">
          ← عودة إلى المسودات
        </Link>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-ink">{p.tender_title}</h1>
        <p className="mt-1 text-xs text-muted" dir="ltr">{p.reference_number}</p>
      </div>
      <article className="whitespace-pre-wrap rounded-lg border bg-surface p-6 text-sm leading-7 text-ink">
        {p.content}
      </article>
      <p className="text-xs text-muted">
        مسودة أولية — راجعها وأكملها قبل التقديم. انسخ النص إلى محرر مستنداتك للمتابعة.
      </p>
      <Link href="/proposals" className="inline-block text-sm text-ink-2 hover:text-ink">
        ← عودة إلى المسودات
      </Link>
    </div>
  );
}
