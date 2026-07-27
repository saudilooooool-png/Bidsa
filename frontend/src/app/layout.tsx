import type { Metadata } from "next";
import Nav from "@/components/Nav";
import "./globals.css";

// Demo vs live mode is decided by API_URL at REQUEST time, so pages must not
// be statically baked at build time (a build without API_URL would otherwise
// freeze demo-mode HTML into the bundle and ignore the runtime env).
export const dynamic = "force-dynamic";

// Live mode renders on the server, so a sleeping free-tier backend (Render
// sleeps after ~15 min idle; waking takes up to ~50s) is billed against this
// function's budget. Raise the ceiling so the first request after a sleep
// waits for the wake-up instead of timing out into the error boundary.
export const maxDuration = 60;

export const metadata: Metadata = {
  title: "بيدسا — استخبارات المشتريات الحكومية",
  description:
    "منصة استخبارات منافسات وترسيات اعتماد: تحليل الجهات، التسعير المعياري، خريطة المنافسة، ورادار مقاولي الباطن.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl" suppressHydrationWarning>
      <body>
        <Nav />
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 pb-8 pt-4 text-xs text-muted">
          المصدر: بيانات منصة اعتماد (المستودع التاريخي). المبالغ بالريال السعودي، محفوظة بالهللات الصحيحة.
        </footer>
      </body>
    </html>
  );
}
