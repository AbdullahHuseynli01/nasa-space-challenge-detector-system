"use client";

import { motion } from "framer-motion";
import { useId, type KeyboardEvent, type ReactNode } from "react";

import { cn } from "@/lib/cn";

import { springSoft } from "./motion";

export interface SegmentOption<T extends string> {
  readonly value: T;
  readonly label: ReactNode;
  readonly icon?: ReactNode;
  readonly disabled?: boolean;
  readonly hint?: ReactNode;
  readonly title?: string;
}

interface SegmentedProps<T extends string> {
  readonly label: string;
  readonly options: readonly SegmentOption<T>[];
  readonly value: T;
  readonly onChange: (value: T) => void;
  readonly size?: "sm" | "md";
  readonly fullWidth?: boolean;
  /** Hide labels and show icons only (labels stay available to screen readers). */
  readonly iconOnly?: boolean;
  readonly className?: string;
}

/** Sunken clay track with a raised knob that glides to the selected option. */
export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  size = "md",
  fullWidth = false,
  iconOnly = false,
  className,
}: SegmentedProps<T>) {
  const knobId = useId();
  const enabled = options.filter((option) => !option.disabled);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
    if (!step || enabled.length === 0) return;
    event.preventDefault();
    const index = enabled.findIndex((option) => option.value === value);
    const next = enabled[(index + step + enabled.length) % enabled.length];
    if (next) onChange(next.value);
  };

  return (
    <div
      role="radiogroup"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={cn(
        "relative items-center gap-1 rounded-[18px] bg-well p-1.5 shadow-well",
        fullWidth ? "flex w-full" : "inline-flex",
        className,
      )}
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <motion.button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={iconOnly && typeof option.label === "string" ? option.label : undefined}
            tabIndex={selected ? 0 : -1}
            disabled={option.disabled}
            title={option.title ?? (iconOnly && typeof option.label === "string" ? option.label : undefined)}
            onClick={() => onChange(option.value)}
            whileTap={option.disabled ? undefined : { scale: 0.95 }}
            className={cn(
              "relative inline-flex items-center justify-center gap-2 rounded-[13px] font-semibold whitespace-nowrap outline-none",
              "transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-accent/50",
              size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2 text-sm",
              iconOnly && (size === "sm" ? "px-2" : "px-2.5"),
              fullWidth && "flex-1",
              selected ? "text-ink" : "text-ink-muted",
              !selected && !option.disabled && "hover:text-ink",
              option.disabled && "cursor-not-allowed opacity-50",
            )}
          >
            {selected && (
              <motion.span
                layoutId={knobId}
                aria-hidden
                className="absolute inset-0 rounded-[13px] bg-surface shadow-clay-sm"
                transition={springSoft}
              />
            )}
            <span className="relative z-10 inline-flex items-center gap-2">
              {option.icon}
              {!iconOnly && option.label}
              {option.hint}
            </span>
          </motion.button>
        );
      })}
    </div>
  );
}
