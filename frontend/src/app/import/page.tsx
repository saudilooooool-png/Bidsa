import ImportClient from "./ImportClient";

// Operator bridge page. Not linked in the public nav — reach it at /import.
export default function ImportPage() {
  const apiBase = process.env.API_URL ?? "https://bidsa-api.onrender.com";
  return (
    <div className="mx-auto max-w-3xl space-y-5 py-4">
      <div>
        <h1 className="text-xl font-bold text-ink">استيراد المنافسات (أداة المشغّل)</h1>
        <p className="mt-2 text-sm text-ink-2">
          جسر مؤقت لجلب المنافسات المفتوحة من متصفحك الحقيقي المسجّل في اعتماد — إلى أن يتوفر
          مصدر بيانات رسمي. يعمل من جلستك المصرّح بها، فلا يعترضه جدار الحماية.
        </p>
      </div>

      <ol className="list-decimal space-y-2 rounded-lg border bg-surface p-4 pe-8 text-sm text-ink-2">
        <li>اضبط متغيّر <code dir="ltr" className="rounded bg-page px-1">INGEST_TOKEN</code> في خادم Render بسلسلة عشوائية طويلة، والصقها أدناه.</li>
        <li>اسحب الزر المتولّد إلى شريط المفضلة في متصفحك.</li>
        <li>افتح صفحة المنافسات في <span dir="ltr">tenders.etimad.sa</span> وسجّل الدخول.</li>
        <li>اضغط زر «استيراد منافسات بيدسا» — يقرأ المنافسات ويرسلها لقاعدتك، وتظهر رسالة بالعدد.</li>
        <li>كرّرها يوميًا (أو أي وقت) للتحديث. البيانات تظهر فورًا في صفحة المطابقة.</li>
      </ol>

      <ImportClient defaultApiBase={apiBase} />

      <p className="text-xs text-muted">
        ملاحظة أمنية: المفتاح السري يبقى في متصفحك وداخل الإشارة المرجعية فقط — لا يُحفظ في المستودع.
        هذه أداة للمشغّل، لا ميزة لكل مستخدم.
      </p>
    </div>
  );
}
