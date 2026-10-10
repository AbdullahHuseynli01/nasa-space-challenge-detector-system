import type { Transition, Variants } from "framer-motion";

/** Shared motion vocabulary: soft, springy, never flashy. */

export const EASE_OUT_EXPO = [0.22, 1, 0.36, 1] as const;

export const springSoft: Transition = { type: "spring", stiffness: 300, damping: 30 };
export const springPress: Transition = { type: "spring", stiffness: 500, damping: 30 };

/** Fade + rise for swapping views (use inside AnimatePresence). */
export const fadeUp = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -6, transition: { duration: 0.15 } },
  transition: { duration: 0.4, ease: EASE_OUT_EXPO },
} as const;

export const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07, delayChildren: 0.05 } },
};

export const rise: Variants = {
  hidden: { opacity: 0, y: 14, scale: 0.98 },
  show: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.55, ease: EASE_OUT_EXPO } },
};
