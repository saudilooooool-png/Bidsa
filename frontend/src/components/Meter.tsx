/**
 * Severity meter: fill color carries severity, unfilled track is a lighter
 * step of the same context; the numeric label always accompanies the color
 * (never color alone).
 */
export default function Meter({
  pct: value,
  label,
}: {
  pct: number | null;
  label: string;
}) {
  if (value == null) return <span className="text-muted">—</span>;
  const fill =
    value >= 40 ? "var(--status-critical)" : value >= 20 ? "var(--status-serious)" : "var(--series-1)";
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 overflow-hidden rounded bg-[color:var(--series-1-soft)]">
        <div
          className="h-full rounded"
          style={{ width: `${Math.min(100, value)}%`, background: fill }}
        />
      </div>
      <span className="tnum text-xs text-ink-2">{label}</span>
    </div>
  );
}
