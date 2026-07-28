"use client";

import { useMemo, useState } from "react";

// Built at runtime from the operator's inputs; the secret never leaves their
// browser and is not stored in the repo.
function buildBookmarklet(apiBase: string, token: string, pages: number): string {
  const src = `(async()=>{
    const API=${JSON.stringify(apiBase)},T=${JSON.stringify(token)},MAX=${pages};
    if(!location.host.includes("etimad.sa")){alert("افتح صفحة المنافسات في اعتماد أولًا ثم اضغط الزر.");return;}
    let all=[];
    for(let p=1;p<=MAX;p++){
      let r,j;
      try{
        r=await fetch("/Tender/AllSupplierTendersForVisitorAsync?PageNumber="+p+"&PageSize=50&IsSearch=true&SortDirection=DESC&Sort=SubmitionDate",{headers:{"X-Requested-With":"XMLHttpRequest"},credentials:"same-origin"});
        j=await r.json();
      }catch(e){alert("تعذّر قراءة الصفحة "+p+" — تأكد أنك مسجّل الدخول في اعتماد.");break;}
      const items=(j&&j.data)||[];
      if(!items.length)break;
      all=all.concat(items);
    }
    if(!all.length){alert("لم يتم العثور على منافسات.");return;}
    const resp=await fetch(API+"/api/v1/ingest/push",{method:"POST",headers:{"Content-Type":"application/json","X-Ingest-Token":T},body:JSON.stringify({items:all})});
    const out=await resp.json().catch(()=>({}));
    alert(resp.ok?("تم الاستيراد ✓\\nجديدة: "+out.created+" | محدّثة: "+out.updated+" | الإجمالي: "+out.total):("فشل: "+(out.detail||resp.status)));
  })();`;
  return "javascript:" + encodeURIComponent(src.replace(/\s+/g, " ").trim());
}

export default function ImportClient({ defaultApiBase }: { defaultApiBase: string }) {
  const [apiBase, setApiBase] = useState(defaultApiBase);
  const [token, setToken] = useState("");
  const [pages, setPages] = useState(10);
  const [copied, setCopied] = useState(false);

  const bookmarklet = useMemo(
    () => (token ? buildBookmarklet(apiBase.replace(/\/$/, ""), token, pages) : ""),
    [apiBase, token, pages],
  );

  const input = "w-full rounded border bg-surface px-3 py-2 text-sm text-ink";

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm text-ink-2">
          رابط الخادم (API)
          <input className={`mt-1 ${input}`} value={apiBase} onChange={(e) => setApiBase(e.target.value)} dir="ltr" />
        </label>
        <label className="text-sm text-ink-2">
          مفتاح الاستيراد السري (INGEST_TOKEN)
          <input
            className={`mt-1 ${input}`}
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="الصق المفتاح الذي ضبطته في الخادم"
            dir="ltr"
          />
        </label>
        <label className="text-sm text-ink-2">
          عدد الصفحات لكل استيراد (24 منافسة/صفحة)
          <input
            type="number" min={1} max={50} className={`mt-1 ${input}`}
            value={pages} onChange={(e) => setPages(Math.max(1, Number(e.target.value) || 1))}
          />
        </label>
      </div>

      {token ? (
        <div className="space-y-3 rounded-lg border bg-surface p-4">
          <p className="text-sm text-ink-2">
            اسحب الزر التالي إلى شريط المفضلة في متصفحك (أو انسخ الرابط وأنشئ إشارة مرجعية يدويًا):
          </p>
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
          <a
            href={bookmarklet}
            onClick={(e) => e.preventDefault()}
            className="inline-block rounded border bg-accent px-4 py-2 text-sm text-white"
            draggable
          >
            ⬇ استيراد منافسات بيدسا
          </a>
          <div className="flex items-center gap-2">
            <button
              onClick={async () => {
                await navigator.clipboard.writeText(bookmarklet);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
              className="rounded border px-3 py-1 text-xs text-ink-2 hover:text-ink"
            >
              {copied ? "نُسخ ✓" : "نسخ رابط الزر"}
            </button>
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted">أدخل المفتاح السري لتوليد الزر.</p>
      )}
    </div>
  );
}
