import { Suspense } from "react";

import { Dashboard } from "@/components/dashboard/dashboard";

export default function HomePage() {
  // Dashboard reads `useSearchParams`, which requires a Suspense boundary
  // for the page to stay statically prerendered.
  return (
    <Suspense>
      <Dashboard />
    </Suspense>
  );
}
