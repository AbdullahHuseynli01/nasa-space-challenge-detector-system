import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { QueryClient, type Query } from "@tanstack/react-query";
import type { PersistQueryClientProviderProps } from "@tanstack/react-query-persist-client";

import { QUERY_SCOPE } from "./keys";

const HOUR = 60 * 60 * 1000;

/**
 * Persisted caches are discarded when this changes: bump the version after a
 * contract change; the fingerprint changes when the app targets another backend.
 */
const CACHE_BUSTER = `nasa-dashboard@1:${process.env.NEXT_PUBLIC_BACKEND_FINGERPRINT ?? "default"}`;
const CACHE_MAX_AGE = 24 * HOUR;

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Analyses and explanations are deterministic for a given key, and the
        // backend allows only a few requests per window: never refetch implicitly.
        staleTime: Number.POSITIVE_INFINITY,
        gcTime: CACHE_MAX_AGE,
        refetchOnWindowFocus: false,
        refetchOnReconnect: false,
        // Every retry spends rate-limit budget; failures are surfaced to the UI,
        // which offers an explicit (or countdown-driven) retry instead.
        retry: false,
      },
    },
  });
}

function shouldPersist(query: Query): boolean {
  return query.state.status === "success" && query.queryKey[0] === QUERY_SCOPE;
}

/** localStorage persistence; a no-op on the server, where `window` is undefined. */
export function createPersistOptions(): PersistQueryClientProviderProps["persistOptions"] {
  return {
    persister: createSyncStoragePersister({
      storage: typeof window === "undefined" ? undefined : window.localStorage,
      key: "nasa-dashboard-cache",
    }),
    maxAge: CACHE_MAX_AGE,
    buster: CACHE_BUSTER,
    dehydrateOptions: { shouldDehydrateQuery: shouldPersist },
  };
}
