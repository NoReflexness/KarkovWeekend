"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const next = (theme === "dark" || resolvedTheme === "dark") ? "light" : "dark";
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label="Skift tema"
      onClick={() => setTheme(next)}
    >
      <Sun className="size-5 dark:hidden" />
      <Moon className="hidden size-5 dark:block" />
    </Button>
  );
}
