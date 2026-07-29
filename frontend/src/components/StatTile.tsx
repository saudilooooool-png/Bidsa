/** Stat tile per the dataviz contract: label · value (semibold, compact) · optional hint. */
export default function StatTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border bg-surface p-4 shadow-card">
      <div className="text-sm text-ink-2">{label}</div>
      <div className="tnum mt-1 text-2xl font-semibold text-ink">{value}</div>
      {hint ? <div className="mt-1 text-xs text-muted">{hint}</div> : null}
    </div>
  );
}
