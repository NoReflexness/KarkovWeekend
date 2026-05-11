"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo } from "react";
import {
  Calendar,
  Home,
  Image as ImageIcon,
  LogOut,
  MessageCircle,
  Settings,
  User as UserIcon,
  Users,
} from "lucide-react";

import { useAuth } from "@/lib/auth";
import { da } from "@/i18n/da";
import { cn } from "@/lib/utils";
import { publicUrl } from "@/lib/format";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ThemeToggle } from "@/components/theme-toggle";
import { NotifyOptInPrompt } from "@/components/notify-opt-in-prompt";
import { Skeleton } from "@/components/ui/skeleton";

const BASE_NAV = [
  { href: "/", label: da.nav.home, icon: Home },
  { href: "/arrangementer", label: da.nav.events, icon: Calendar },
  { href: "/galleri", label: da.nav.gallery, icon: ImageIcon },
  { href: "/chat", label: da.nav.chat, icon: MessageCircle },
  { href: "/familie", label: da.nav.family, icon: Users },
  { href: "/profil", label: da.nav.profile, icon: UserIcon },
];
const ADMIN_EXTRA = { href: "/indstillinger", label: da.nav.settings, icon: Settings };

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      const next = encodeURIComponent(pathname || "/");
      router.replace(`/login?next=${next}`);
    }
  }, [loading, user, pathname, router]);

  const NAV = useMemo(
    () => (user?.role === "admin" ? [...BASE_NAV, ADMIN_EXTRA] : BASE_NAV),
    [user?.role],
  );

  if (loading || !user) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <Skeleton className="size-16 rounded-full" />
      </div>
    );
  }

  const initials = user.name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <div className="flex min-h-svh flex-col">
      <header className="glass-nav sticky top-0 z-30 border-b">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <Link
            href="/"
            className="from-primary to-primary/60 dark:from-primary dark:to-primary/40 bg-gradient-to-r bg-clip-text text-lg font-semibold tracking-tight text-transparent"
          >
            {da.app.name}
          </Link>
          <nav className="hidden items-center gap-1 md:flex">
            {NAV.map((item) => {
              const Icon = item.icon;
              const active =
                pathname === item.href ||
                (item.href !== "/" && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "hover:bg-accent/60 hover:text-accent-foreground rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors",
                    active &&
                      "bg-accent/80 text-accent-foreground ring-foreground/5 ring-1",
                  )}
                >
                  <span className="flex items-center gap-2">
                    <Icon className="size-4" />
                    {item.label}
                  </span>
                </Link>
              );
            })}
          </nav>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Profil menu">
                  <Avatar className="size-8">
                    {user.profile_picture_url && (
                      <AvatarImage src={publicUrl(user.profile_picture_url)} alt={user.name} />
                    )}
                    <AvatarFallback>{initials || "?"}</AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem asChild>
                  <Link href="/profil">{da.nav.profile}</Link>
                </DropdownMenuItem>
                {user.role === "admin" && (
                  <DropdownMenuItem asChild>
                    <Link href="/indstillinger">{da.nav.settings}</Link>
                  </DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => void logout()}>
                  <LogOut className="size-4" />
                  {da.nav.logout}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 pb-24 md:pb-10">
        {children}
      </main>
      <NotifyOptInPrompt />
      <nav
        className="glass-nav fixed bottom-0 left-0 right-0 z-30 grid border-t md:hidden"
        style={{ gridTemplateColumns: `repeat(${NAV.length}, minmax(0, 1fr))` }}
      >
        {NAV.map((item) => {
          const Icon = item.icon;
          const active =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "text-muted-foreground relative flex flex-col items-center justify-center gap-1 py-3 text-xs transition-colors",
                active && "text-primary",
              )}
            >
              {active && (
                <span className="bg-primary/10 absolute inset-x-3 inset-y-2 rounded-2xl" />
              )}
              <Icon className="size-5 relative" />
              <span className="relative">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
