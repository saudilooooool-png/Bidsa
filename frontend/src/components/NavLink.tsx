"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Nav link that highlights when it matches the current route. `strong` marks
 *  workspace (authenticated) links, which read heavier than intel links. */
export default function NavLink({
  href,
  label,
  strong = false,
}: {
  href: string;
  label: string;
  strong?: boolean;
}) {
  const pathname = usePathname();
  const active = href === "/" ? pathname === "/" : pathname.startsWith(href);

  const base = "rounded-md px-2 py-1 transition-colors";
  const tone = active
    ? "bg-accent-soft font-semibold text-ink"
    : strong
      ? "font-medium text-ink hover:bg-accent-soft/60"
      : "text-ink-2 hover:bg-accent-soft/60 hover:text-ink";

  return (
    <Link href={href} aria-current={active ? "page" : undefined} className={`${base} ${tone}`}>
      {label}
    </Link>
  );
}
