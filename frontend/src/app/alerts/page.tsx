import { authFetch } from "@/lib/session";
import { api } from "@/lib/api";
import AlertsClient from "@/components/AlertsClient";

export const dynamic = "force-dynamic";

export interface Alert {
  id: string;
  name: string;
  keywords: string | null;
  activity_id: number | null;
  region_id: number | null;
  notify_email: boolean;
  last_notified_at: string | null;
}

export default async function AlertsPage() {
  const [alerts, lookups] = await Promise.all([
    authFetch<Alert[]>("/api/v1/alerts"),
    api.lookups(),
  ]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-ink">تنبيهات المنافسات</h1>
        <p className="mt-1 text-sm text-ink-2">
          احفظ عمليات بحث بمعايير تهمّك، ونرسل لك بريدًا عند نزول منافسات جديدة مطابقة.
        </p>
      </div>
      <AlertsClient
        initial={alerts ?? []}
        activities={lookups.activities.slice(0, 80)}
        regions={lookups.regions.slice(0, 40)}
        loggedIn={alerts !== null}
      />
    </div>
  );
}
