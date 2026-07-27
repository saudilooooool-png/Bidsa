"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

interface Doc {
  id: string; title: string; filename: string | null;
  chunks: number; created_at: string;
}
interface Match {
  tender_id: string; reference_number: string; title: string;
  agency: string | null; award_sar: number | null; score: number;
  details_url: string | null;
}

const btn = "rounded border bg-accent px-4 py-2 text-sm text-white disabled:opacity-50";

export default function MatchingClient({ docs }: { docs: Doc[] }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [matches, setMatches] = useState<Match[] | null>(null);
  const [generated, setGenerated] = useState<Record<string, string>>({});

  async function call(path: string, init?: RequestInit) {
    const res = await fetch(`/api/proxy/${path}`, { method: "POST", ...init });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "خطأ غير متوقع");
    return data;
  }

  async function upload(form: HTMLFormElement) {
    const fd = new FormData(form);
    setBusy("upload"); setError(null);
    try {
      await call("knowledge/upload", { body: fd });
      form.reset();
      router.refresh();
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(null); }
  }

  async function runMatch() {
    setBusy("match"); setError(null);
    try {
      const data = await call("knowledge/match");
      setKeywords(data.profile_keywords ?? []);
      setMatches(data.matches ?? []);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(null); }
  }

  async function generate(tenderId: string) {
    setBusy(tenderId); setError(null);
    try {
      const data = await call("proposals/generate", {
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tender_id: tenderId }),
      });
      setGenerated((g) => ({ ...g, [tenderId]: data.id }));
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(null); }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-lg border bg-surface p-4">
        <h2 className="text-base font-semibold text-ink">1 · ملفات شركتك</h2>
        <p className="mt-0.5 text-xs text-muted">
          ارفع الملف التعريفي وسابقة الأعمال (txt / md / pdf، حتى 8MB) — منها نبني بصمة نشاطك.
        </p>
        {docs.length > 0 ? (
          <ul className="mt-3 space-y-1 text-sm text-ink-2">
            {docs.map((d) => (
              <li key={d.id}>📄 {d.title} <span className="text-muted">({d.chunks} مقطعًا)</span></li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-muted">لا ملفات بعد.</p>
        )}
        <form
          className="mt-3 flex flex-wrap items-center gap-2"
          onSubmit={(e) => { e.preventDefault(); upload(e.currentTarget); }}
        >
          <input type="file" name="file" accept=".txt,.md,.pdf" required
                 className="text-sm text-ink-2" />
          <button className={btn} disabled={busy === "upload"}>
            {busy === "upload" ? "جارٍ الرفع…" : "رفع"}
          </button>
        </form>
      </section>

      <section className="rounded-lg border bg-surface p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-ink">2 · المطابقة</h2>
            <p className="mt-0.5 text-xs text-muted">
              نطابق بصمة شركتك مع مستودع 55 ألف منافسة ونرتبها بالأنسب.
            </p>
          </div>
          <button className={btn} onClick={runMatch} disabled={busy === "match" || docs.length === 0}>
            {busy === "match" ? "جارٍ التحليل…" : "شغّل المطابقة"}
          </button>
        </div>

        {keywords.length > 0 ? (
          <p className="mt-3 text-xs text-muted">
            بصمة النشاط: {keywords.slice(0, 8).join(" · ")}
          </p>
        ) : null}

        {matches !== null ? (
          matches.length === 0 ? (
            <p className="mt-3 text-sm text-muted">لا نتائج — أثرِ ملفاتك بمفردات نشاطك.</p>
          ) : (
            <table className="mt-3 w-full text-sm">
              <thead>
                <tr className="border-b text-right text-xs text-muted">
                  <th className="py-1 font-normal">المنافسة</th>
                  <th className="py-1 font-normal">الجهة</th>
                  <th className="py-1 font-normal">قيمة الترسية</th>
                  <th className="py-1 font-normal">RFP</th>
                </tr>
              </thead>
              <tbody>
                {matches.map((m) => (
                  <tr key={m.tender_id} className="border-b border-grid last:border-0">
                    <td className="max-w-[22rem] py-2 text-ink" title={m.title}>
                      <span className="line-clamp-2">{m.title}</span>
                    </td>
                    <td className="max-w-[10rem] truncate py-2 text-ink-2">{m.agency ?? "—"}</td>
                    <td className="tnum whitespace-nowrap py-2 text-ink-2">
                      {m.award_sar != null ? `${(m.award_sar / 1e6).toLocaleString("ar-SA-u-nu-latn", { maximumFractionDigits: 1 })} مليون` : "—"}
                    </td>
                    <td className="py-2">
                      {generated[m.tender_id] ? (
                        <Link href={`/proposals/${generated[m.tender_id]}`} className="text-accent hover:underline">
                          عرض المسودة ←
                        </Link>
                      ) : (
                        <button
                          className="rounded border px-3 py-1 text-xs text-ink-2 hover:text-ink disabled:opacity-50"
                          onClick={() => generate(m.tender_id)}
                          disabled={busy === m.tender_id}
                        >
                          {busy === m.tender_id ? "..." : "ولّد مسودة"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : null}
      </section>

      {error ? <p className="text-sm text-critical">{error}</p> : null}
    </div>
  );
}
