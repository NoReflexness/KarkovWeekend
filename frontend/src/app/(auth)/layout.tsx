import type { ReactNode } from "react";
import Link from "next/link";

import { da } from "@/i18n/da";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-svh flex-col items-center justify-center overflow-hidden p-6">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -left-32 -top-32 size-[28rem] rounded-full bg-sky-400/30 blur-3xl dark:bg-sky-500/20" />
        <div className="absolute -right-24 top-1/3 size-[26rem] rounded-full bg-fuchsia-400/25 blur-3xl dark:bg-fuchsia-500/20" />
        <div className="absolute bottom-0 left-1/3 size-[28rem] rounded-full bg-emerald-300/25 blur-3xl dark:bg-emerald-500/15" />
      </div>
      <Link
        href="/"
        className="from-primary to-primary/60 mb-8 bg-gradient-to-r bg-clip-text text-2xl font-semibold tracking-tight text-transparent"
      >
        {da.app.name}
      </Link>
      <div className="glass-strong w-full max-w-sm rounded-3xl p-6 sm:p-8">
        {children}
      </div>
    </div>
  );
}
