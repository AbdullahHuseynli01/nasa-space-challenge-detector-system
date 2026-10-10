"use client";

import { useEffect, useState } from "react";

/** True once `active` has stayed true for `delayMs`; resets as soon as it turns false. */
export function useDelayedFlag(active: boolean, delayMs: number): boolean {
  const [elapsed, setElapsed] = useState(false);

  useEffect(() => {
    if (!active) return;
    const id = window.setTimeout(() => setElapsed(true), delayMs);
    return () => {
      window.clearTimeout(id);
      setElapsed(false);
    };
  }, [active, delayMs]);

  return active && elapsed;
}
