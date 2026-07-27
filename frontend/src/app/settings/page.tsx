import { authFetch, currentUser } from "@/lib/session";
import { num } from "@/lib/format";
import Panel from "@/components/Panel";
import StatTile from "@/components/StatTile";
import { AddMemberForm, LogoutButton, UpgradeButtons } from "@/components/SettingsClient";

interface TeamOut {
  seats_limit: number;
  members: { id: string; email: string; full_name: string | null; role: string; is_active: boolean }[];
}

const ROLE_AR: Record<string, string> = { owner: "مالك", admin: "مشرف", member: "عضو" };
const STATE_AR: Record<string, string> = { trial: "تجربة مجانية", active: "نشط", expired: "منتهٍ" };

export default async function SettingsPage() {
  const me = await currentUser();
  if (!me) {
    return <p className="text-sm text-muted">انتهت الجلسة — سجّل الدخول مجددًا.</p>;
  }
  const team = await authFetch<TeamOut>("/api/v1/team/members");
  const sub = me.subscription;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-ink">{me.company}</h1>
          <p className="mt-1 text-sm text-ink-2">
            {me.full_name} · {ROLE_AR[me.role] ?? me.role} · <span dir="ltr">{me.email}</span>
          </p>
        </div>
        <LogoutButton />
      </div>

      <Panel title="الاشتراك" subtitle="حالة خطتك الحالية">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          <StatTile label="الحالة" value={STATE_AR[sub.state] ?? sub.state} />
          <StatTile label="الخطة" value={sub.plan === "trial" ? "تجريبية" : sub.plan} />
          {sub.trial_days_left != null ? (
            <StatTile label="المتبقي من التجربة" value={`${num(sub.trial_days_left)} يومًا`} />
          ) : null}
        </div>
        {sub.state !== "active" && (me.role === "owner" || me.role === "admin") ? (
          <div className="mt-4">
            <UpgradeButtons plans={[
              { key: "starter", name: "الأساسية (499 ر.س)" },
              { key: "pro", name: "الاحترافية (1,499 ر.س)" },
            ]} />
          </div>
        ) : null}
      </Panel>

      <Panel
        title="الفريق"
        subtitle={team ? `${team.members.filter((m) => m.is_active).length} من ${team.seats_limit} مقعدًا` : ""}
      >
        {team ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-right text-xs text-muted">
                <th className="py-1 font-normal">الاسم</th>
                <th className="py-1 font-normal">البريد</th>
                <th className="py-1 font-normal">الدور</th>
                <th className="py-1 font-normal">الحالة</th>
              </tr>
            </thead>
            <tbody>
              {team.members.map((m) => (
                <tr key={m.id} className="border-b border-grid last:border-0">
                  <td className="py-2 text-ink">{m.full_name ?? "—"}</td>
                  <td className="py-2 text-ink-2" dir="ltr">{m.email}</td>
                  <td className="py-2 text-ink-2">{ROLE_AR[m.role] ?? m.role}</td>
                  <td className="py-2 text-ink-2">{m.is_active ? "نشط" : "معطّل"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-muted">تعذر جلب الفريق.</p>
        )}
        {me.role === "owner" || me.role === "admin" ? (
          <div className="mt-4 border-t pt-4">
            <h3 className="mb-2 text-sm font-semibold text-ink">إضافة عضو</h3>
            <AddMemberForm />
          </div>
        ) : null}
      </Panel>
    </div>
  );
}
