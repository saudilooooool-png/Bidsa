export default function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border bg-surface p-4">
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      {subtitle ? <p className="mt-0.5 text-xs text-muted">{subtitle}</p> : null}
      <div className="mt-3">{children}</div>
    </section>
  );
}
