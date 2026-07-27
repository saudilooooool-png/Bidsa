import Link from "next/link";
import { IS_DEMO } from "@/lib/api";
import { currentUser } from "@/lib/session";
import { num } from "@/lib/format";

const intelItems = [
  { href: "/", label: "الرئيسية" },
  { href: "/agencies", label: "الجهات" },
  { href: "/companies", label: "الشركات" },
  { href: "/pricing", label: "التسعير المعياري" },
  { href: "/competition", label: "خريطة المنافسة" },
  { href: "/matchmaking", label: "رادار الباطن" },
];

const workspaceItems = [
  { href: "/matching", label: "المطابقة و RFP" },
  { href: "/proposals", label: "مسوداتي" },
  { href: "/settings", label: "الإعدادات" },
];

export default async function Nav() {
  const me = IS_DEMO ? null : await currentUser();
  return (
    <header className="border-b bg-surface">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="text-lg font-bold text-ink">
          بيدسا <span className="font-normal text-ink-2">| استخبارات المشتريات</span>
        </Link>
        {IS_DEMO ? (
          <span className="rounded-full border px-2 py-0.5 text-xs text-ink-2">
            نسخة تجريبية — لقطة تاريخية
          </span>
        ) : null}
        <nav className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {intelItems.map((it) => (
            <Link key={it.href} href={it.href} className="text-ink-2 hover:text-ink">
              {it.label}
            </Link>
          ))}
          {me
            ? workspaceItems.map((it) => (
                <Link key={it.href} href={it.href} className="font-medium text-ink hover:underline">
                  {it.label}
                </Link>
              ))
            : null}
        </nav>
        <div className="ms-auto flex items-center gap-3 text-sm">
          {me ? (
            <span className="text-xs text-ink-2">
              {me.company}
              {me.subscription.state === "trial" && me.subscription.trial_days_left != null ? (
                <span className="text-muted"> · تجربة: {num(me.subscription.trial_days_left)} يومًا</span>
              ) : null}
            </span>
          ) : IS_DEMO ? null : (
            <>
              <Link href="/plans" className="text-ink-2 hover:text-ink">الأسعار</Link>
              <Link href="/login" className="text-ink-2 hover:text-ink">دخول</Link>
              <Link
                href="/register"
                className="rounded border bg-accent px-3 py-1 text-white"
              >
                تجربة مجانية
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
