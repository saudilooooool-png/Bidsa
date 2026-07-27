import Link from "next/link";
import { num } from "@/lib/format";

const API_URL = process.env.API_URL;

interface PlanRow {
  key: string;
  name: string;
  price_sar_month: number | null;
  seats: number;
  proposals_per_month: number | null;
  features: string[];
}

// Mirror of backend/app/core/plans.py — used when no backend is attached.
const FALLBACK: PlanRow[] = [
  { key: "starter", name: "الأساسية", price_sar_month: 499, seats: 3, proposals_per_month: 10,
    features: ["كل لوحات الاستخبارات", "مطابقة المناقصات من ملف الشركة", "10 مسودات RFP شهريًا", "3 مستخدمين"] },
  { key: "pro", name: "الاحترافية", price_sar_month: 1499, seats: 15, proposals_per_month: null,
    features: ["كل مزايا الأساسية", "مسودات RFP غير محدودة", "15 مستخدمًا", "أولوية في الدعم"] },
  { key: "enterprise", name: "المنشآت", price_sar_month: null, seats: 100, proposals_per_month: null,
    features: ["كل مزايا الاحترافية", "واجهة API للبيانات (DaaS)", "مستخدمون غير محدودين عمليًا", "اتفاقية مستوى خدمة"] },
];

async function loadPlans(): Promise<PlanRow[]> {
  if (!API_URL) return FALLBACK;
  try {
    const res = await fetch(`${API_URL}/api/v1/billing/plans`, { cache: "no-store" });
    if (!res.ok) return FALLBACK;
    return (await res.json()).plans as PlanRow[];
  } catch {
    return FALLBACK;
  }
}

export default async function PlansPage() {
  const plans = await loadPlans();
  return (
    <div className="space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-ink">الأسعار</h1>
        <p className="mt-2 text-sm text-ink-2">
          كل الخطط تبدأ بتجربة مجانية كاملة المزايا لمدة 14 يومًا — بلا بطاقة ائتمانية.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {plans.map((p) => (
          <div
            key={p.key}
            className={`flex flex-col rounded-lg border bg-surface p-5 ${p.key === "pro" ? "ring-2 ring-[color:var(--series-1)]" : ""}`}
          >
            <div className="flex items-baseline justify-between">
              <h2 className="text-lg font-bold text-ink">{p.name}</h2>
              {p.key === "pro" ? (
                <span className="rounded-full border px-2 py-0.5 text-xs text-ink-2">الأكثر طلبًا</span>
              ) : null}
            </div>
            <div className="mt-3 text-3xl font-semibold text-ink">
              {p.price_sar_month != null ? (
                <>
                  {num(p.price_sar_month)}{" "}
                  <span className="text-base font-normal text-ink-2">ر.س / شهريًا</span>
                </>
              ) : (
                <span className="text-xl">تواصل معنا</span>
              )}
            </div>
            <ul className="mt-4 flex-1 space-y-2 text-sm text-ink-2">
              {p.features.map((f) => (
                <li key={f} className="flex gap-2">
                  <span className="text-good">✓</span> {f}
                </li>
              ))}
            </ul>
            <Link
              href="/register"
              className="mt-5 rounded border bg-accent px-4 py-2 text-center text-sm text-white"
            >
              ابدأ التجربة المجانية
            </Link>
          </div>
        ))}
      </div>

      <p className="text-center text-xs text-muted">
        الدفع الإلكتروني قادم قريبًا — عند انتهاء التجربة يتواصل فريقنا لتفعيل الخطة المناسبة.
      </p>
    </div>
  );
}
