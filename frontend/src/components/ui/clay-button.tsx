"use client";

import { motion, type HTMLMotionProps } from "framer-motion";

import { cn } from "@/lib/cn";

import { springPress } from "./motion";

const VARIANT = {
  primary: "bg-accent text-white shadow-clay-accent",
  soft: "bg-surface text-ink shadow-clay-sm",
} as const;

interface ClayButtonProps extends HTMLMotionProps<"button"> {
  readonly variant?: keyof typeof VARIANT;
}

/** Clay button: lifts on hover, squishes into the surface when pressed. */
export function ClayButton({ variant = "primary", className, disabled, ...props }: ClayButtonProps) {
  return (
    <motion.button
      type="button"
      disabled={disabled}
      whileHover={disabled ? undefined : { y: -2 }}
      whileTap={disabled ? undefined : { y: 1, scale: 0.97 }}
      transition={springPress}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-semibold whitespace-nowrap",
        "outline-none focus-visible:ring-2 focus-visible:ring-accent/50 focus-visible:ring-offset-2 focus-visible:ring-offset-surface",
        "active:shadow-well disabled:cursor-not-allowed disabled:opacity-55",
        VARIANT[variant],
        className,
      )}
      {...props}
    />
  );
}
