"use client";

/**
 * Global error boundary — most commonly hit when the intel API is not
 * reachable (e.g. frontend deployed on Vercel before API_URL is set).
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto max-w-xl rounded-lg border bg-surface p-8 text-center">
      <h2 className="text-lg font-bold text-ink">تعذّر الوصول إلى خادم البيانات</h2>
      <p className="mt-2 text-sm text-ink-2">
        الواجهة تعمل، لكن الاتصال بواجهة الاستخبارات (API) فشل. تأكد من أن الخادم الخلفي
        يعمل وأن متغيّر البيئة <code dir="ltr" className="rounded bg-page px-1">API_URL</code>{" "}
        في إعدادات النشر يشير إليه.
      </p>
      <p className="mt-2 break-all text-xs text-muted" dir="ltr">
        {error.message}
      </p>
      <button
        onClick={reset}
        className="mt-4 rounded border bg-accent px-4 py-2 text-sm text-white"
      >
        إعادة المحاولة
      </button>
    </div>
  );
}
