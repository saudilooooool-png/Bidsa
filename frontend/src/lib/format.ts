/** Arabic-labeled, Latin-digit formatting (Saudi fintech convention). */

const LOCALE = "ar-SA-u-nu-latn";

export function num(v: number | null | undefined, digits = 0): string {
  if (v == null) return "—";
  return v.toLocaleString(LOCALE, { maximumFractionDigits: digits });
}

/** Compact SAR: 8.5 مليار / 12.3 مليون / 45 ألف / 950 */
export function sarCompact(v: number | null | undefined): string {
  if (v == null) return "—";
  const abs = Math.abs(v);
  if (abs >= 1e9) return `${num(v / 1e9, 1)} مليار`;
  if (abs >= 1e6) return `${num(v / 1e6, 1)} مليون`;
  if (abs >= 1e3) return `${num(v / 1e3, 0)} ألف`;
  return num(v, 0);
}

export function sarFull(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${num(v, 0)} ر.س`;
}

export function pct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${num(v, 1)}٪`;
}

export function dateShort(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(LOCALE, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
