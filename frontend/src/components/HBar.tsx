import Link from "next/link";

/**
 * Horizontal magnitude bar (single hue — magnitude job, not identity):
 * ≤24px thick, 4px rounded data-end, square at the baseline, value at the tip.
 * In RTL the baseline sits on the right, so the rounded data-end is the left edge.
 *
 * The bar is absolutely positioned inside a fixed track so its width is a true
 * percentage of the track — a flex layout here lets long value labels shrink
 * bars unevenly and break length comparisons. Bars use ≤72% of the track,
 * reserving the rest for the tip label (proportions are preserved).
 */
export default function HBar({
  label,
  valueLabel,
  fraction,
  href,
}: {
  label: string;
  valueLabel: string;
  fraction: number; // 0..1 of the panel's max
  href?: string;
}) {
  const width = Math.max(2, Math.round(fraction * 72));
  const labelEl = href ? (
    <Link href={href} className="truncate text-sm text-ink hover:underline">
      {label}
    </Link>
  ) : (
    <span className="truncate text-sm text-ink">{label}</span>
  );
  return (
    <div className="grid grid-cols-[minmax(0,14rem)_1fr] items-center gap-3 py-1">
      {labelEl}
      <div className="relative h-4">
        <div
          className="absolute inset-y-0 right-0 rounded-l bg-accent"
          style={{ width: `${width}%` }}
          aria-hidden
        />
        <span
          className="tnum absolute top-1/2 -translate-y-1/2 whitespace-nowrap text-xs text-ink-2"
          style={{ right: `calc(${width}% + 8px)` }}
        >
          {valueLabel}
        </span>
      </div>
    </div>
  );
}
