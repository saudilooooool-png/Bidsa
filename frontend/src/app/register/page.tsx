import Link from "next/link";
import { RegisterForm } from "@/components/AuthForms";

export default function RegisterPage() {
  return (
    <div className="mx-auto max-w-sm space-y-4 py-8">
      <h1 className="text-xl font-bold text-ink">حساب جديد</h1>
      <p className="text-sm text-ink-2">
        تجربة مجانية كاملة المزايا لمدة 14 يومًا — بلا بطاقة ائتمانية.
      </p>
      <div className="rounded-lg border bg-surface p-5">
        <RegisterForm />
      </div>
      <p className="text-sm text-ink-2">
        لديك حساب؟{" "}
        <Link href="/login" className="text-accent hover:underline">سجّل الدخول</Link>
      </p>
    </div>
  );
}
