import Link from "next/link";

const items = [
  { href: "/", label: "الرئيسية" },
  { href: "/agencies", label: "الجهات" },
  { href: "/companies", label: "الشركات" },
  { href: "/pricing", label: "التسعير المعياري" },
  { href: "/competition", label: "خريطة المنافسة" },
  { href: "/matchmaking", label: "رادار الباطن" },
];

export default function Nav() {
  return (
    <header className="border-b bg-surface">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="text-lg font-bold text-ink">
          بيدسا <span className="font-normal text-ink-2">| استخبارات المشتريات</span>
        </Link>
        <nav className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {items.map((it) => (
            <Link key={it.href} href={it.href} className="text-ink-2 hover:text-ink">
              {it.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
