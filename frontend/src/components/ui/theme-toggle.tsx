"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

import { applyTheme, readTheme, subscribeTheme, type Theme } from "@/lib/theme";

import { springPress } from "./motion";

export function ThemeToggle() {
  // Server snapshot is null: the icon renders after hydration, avoiding a mismatch.
  const theme = useSyncExternalStore<Theme | null>(subscribeTheme, readTheme, () => null);
  const next: Theme = theme === "dark" ? "light" : "dark";

  return (
    <motion.button
      type="button"
      onClick={() => applyTheme(next)}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      whileHover={{ y: -2 }}
      whileTap={{ y: 1, scale: 0.94 }}
      transition={springPress}
      className="grid size-11 place-items-center overflow-hidden rounded-2xl bg-surface text-ink-muted shadow-clay-sm outline-none hover:text-ink focus-visible:ring-2 focus-visible:ring-accent/50 active:shadow-well"
    >
      <AnimatePresence mode="wait" initial={false}>
        {theme && (
          <motion.span
            key={theme}
            initial={{ y: 14, opacity: 0, rotate: -40 }}
            animate={{ y: 0, opacity: 1, rotate: 0 }}
            exit={{ y: -14, opacity: 0, rotate: 40 }}
            transition={{ duration: 0.25 }}
            className="inline-flex"
          >
            {theme === "dark" ? <Moon className="size-[18px]" aria-hidden /> : <Sun className="size-[18px]" aria-hidden />}
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  );
}
