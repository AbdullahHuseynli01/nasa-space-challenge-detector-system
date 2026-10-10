"use client";

import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { MotionConfig } from "framer-motion";
import { useState, type ReactNode } from "react";

import { createPersistOptions, createQueryClient } from "@/core/query/client";

export function Providers({ children }: { readonly children: ReactNode }) {
  // One client per browser session; lazily created so SSR never shares state.
  const [queryClient] = useState(createQueryClient);
  const [persistOptions] = useState(createPersistOptions);

  return (
    <PersistQueryClientProvider client={queryClient} persistOptions={persistOptions}>
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
    </PersistQueryClientProvider>
  );
}
