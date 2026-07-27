import { authFetch } from "@/lib/session";
import MatchingClient from "@/components/MatchingClient";

interface Doc {
  id: string; title: string; filename: string | null;
  chunks: number; created_at: string;
}

export default async function MatchingPage() {
  const docs = (await authFetch<Doc[]>("/api/v1/knowledge/documents")) ?? [];
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-ink">مطابقة المناقصات وبناء RFP</h1>
      <p className="text-sm text-ink-2">
        ارفع ملف شركتك، شغّل المطابقة على المستودع، ثم ولّد مسودة عرض فني لأي منافسة بنقرة.
      </p>
      <MatchingClient docs={docs} />
    </div>
  );
}
