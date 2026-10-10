"use client";

import { useCallback, useSyncExternalStore, type RefObject } from "react";

export interface ElementSize {
  readonly width: number;
  readonly height: number;
}

/** Live size of an element, kept current by a ResizeObserver (0 × 0 on the server). */
export function useElementSize(ref: RefObject<HTMLElement | null>): ElementSize {
  const subscribe = useCallback(
    (notify: () => void) => {
      const element = ref.current;
      if (!element) return () => {};
      const observer = new ResizeObserver(notify);
      observer.observe(element);
      return () => observer.disconnect();
    },
    [ref],
  );
  const width = useSyncExternalStore(subscribe, () => Math.floor(ref.current?.clientWidth ?? 0), () => 0);
  const height = useSyncExternalStore(subscribe, () => Math.floor(ref.current?.clientHeight ?? 0), () => 0);
  return { width, height };
}
