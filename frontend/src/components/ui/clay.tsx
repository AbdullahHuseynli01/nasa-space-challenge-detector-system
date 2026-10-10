"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

interface ClayCardProps extends Omit<HTMLMotionProps<"section">, "children"> {
  readonly children?: ReactNode;
}

/** Raised clay surface: puffy, borderless, shaped by light and shadow alone. */
export function ClayCard({ className, children, ...props }: ClayCardProps) {
  return (
    <motion.section
      className={cn(
        "rounded-[28px] bg-surface shadow-clay transition-[box-shadow,background-color] duration-300",
        "hover:shadow-clay-lift",
        className,
      )}
      {...props}
    >
      {children}
    </motion.section>
  );
}

/** Sunken tray for content that sits "inside" a card. */
export function ClayWell({ className, children }: { readonly className?: string; readonly children: ReactNode }) {
  return <div className={cn("rounded-[20px] bg-well shadow-well", className)}>{children}</div>;
}

const BLOB_TONE = {
  accent: "bg-accent-soft text-accent",
  rise: "bg-rise-soft text-rise",
  fall: "bg-fall-soft text-fall",
  caution: "bg-caution-soft text-caution",
  neutral: "bg-well text-ink-muted",
} as const;

/** Small puffy icon bubble. */
export function ClayBlob({
  tone = "accent",
  size = "md",
  className,
  children,
}: {
  readonly tone?: keyof typeof BLOB_TONE;
  readonly size?: "sm" | "md" | "lg";
  readonly className?: string;
  readonly children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-grid shrink-0 place-items-center shadow-clay-sm",
        size === "sm" && "size-8 rounded-xl",
        size === "md" && "size-11 rounded-2xl",
        size === "lg" && "size-14 rounded-[20px]",
        BLOB_TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Eyebrow({ children, className }: { readonly children: ReactNode; readonly className?: string }) {
  return (
    <p className={cn("text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-faint", className)}>
      {children}
    </p>
  );
}
