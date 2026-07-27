import Link from "next/link";
import { LoginForm } from "@/components/AuthForms";

export default function LoginPage() {
  return (
    <div className="mx-auto max-w-sm space-y-4 py-8">
      <h1 className="text-xl font-bold text-ink">تسجيل الدخول</h1>
      <div className="rounded-lg border bg-surface p-5">
        <LoginForm />
      </div>
      <p className="text-sm text-ink-2">
        ليس لديك حساب؟{" "}
        <Link href="/register" className="text-accent hover:underline">
          ابدأ تجربة مجانية 14 يومًا
        </Link>
      </p>
    </div>
  );
}
