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
    <section className="rounded-xl border bg-surface p-4 shadow-card">
      <h2 className="border-s-2 border-accent ps-2 text-base font-semibold leading-tight text-ink">
        {title}
      </h2>
      {subtitle ? <p className="mt-1 text-xs text-muted">{subtitle}</p> : null}
      <div className="mt-3">{children}</div>
    </section>
  );
}
