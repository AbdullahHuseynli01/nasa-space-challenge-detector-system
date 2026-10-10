"use client";

import { KeyRound, RefreshCw, ServerCrash, TriangleAlert, type LucideIcon } from "lucide-react";

import { ClayBlob } from "@/components/ui/clay";
import { ClayButton } from "@/components/ui/clay-button";
import { CountdownRing } from "@/components/ui/countdown-ring";
import { useRateLimitRecovery } from "@/hooks/use-dashboard-queries";
import { isApiError, type ApiErrorKind } from "@/lib/api/errors";
import { cn } from "@/lib/cn";

interface ErrorCopy {
  readonly title: string;
  readonly hint?: string;
  readonly icon: LucideIcon;
  readonly retryable: boolean;
}

const COPY: Readonly<Record<Exclude<ApiErrorKind, "rate_limited">, ErrorCopy>> = {
  network: {
    title: "Can't reach the analysis service",
    hint: "Check that the backend is running. Locally it's set in .env.local; a deployed site must also be listed in the backend's CORS_ORIGINS.",
    icon: ServerCrash,
    retryable: true,
  },
  unavailable: {
    title: "AI explanations aren't configured",
    hint: "Set GROQ_API_KEY in backend/.env and restart the server.",
    icon: KeyRound,
    retryable: false,
  },
  upstream: {
    title: "The model's explanation was rejected",
    hint: "The backend refuses explanations that are incomplete or add unsupported numbers. Try again.",
    icon: TriangleAlert,
    retryable: true,
  },
  validation: { title: "The backend rejected the request", icon: TriangleAlert, retryable: false },
  invalid_payload: { title: "Couldn't prepare a valid request", icon: TriangleAlert, retryable: false },
  invalid_response: { title: "Unexpected response format", icon: TriangleAlert, retryable: true },
  bad_request: { title: "Unsupported request", icon: TriangleAlert, retryable: false },
  server: { title: "The backend hit an error", icon: ServerCrash, retryable: true },
};

interface ErrorStateProps {
  readonly error: unknown;
  readonly onRetry: () => unknown;
  readonly className?: string;
}

/** Uniform error presentation, with a self-retrying countdown for HTTP 429. */
export function ErrorState({ error, onRetry, className }: ErrorStateProps) {
  const { retryAt, secondsLeft, totalSeconds } = useRateLimitRecovery(error, onRetry);

  if (retryAt !== null) {
    return (
      <div
        role="status"
        className={cn(
          "flex flex-col items-start gap-4 rounded-[20px] bg-caution-soft p-5 min-[420px]:flex-row min-[420px]:items-center",
          className,
        )}
      >
        <CountdownRing secondsLeft={secondsLeft} totalSeconds={totalSeconds} />
        <div className="min-w-0 space-y-1">
          <p className="font-semibold text-ink">Taking a short breather</p>
          <p className="text-sm text-ink-muted">
            {secondsLeft > 0
              ? "The backend allows a few requests per window. This retries on its own when the timer ends."
              : "Retrying now…"}
          </p>
        </div>
      </div>
    );
  }

  const copy = isApiError(error) && error.kind !== "rate_limited" ? COPY[error.kind] : COPY.server;
  const message = error instanceof Error ? error.message : "Something went wrong.";
  const Icon = copy.icon;

  return (
    <div role="alert" className={cn("flex flex-wrap items-start gap-4 rounded-[20px] bg-fall-soft p-5", className)}>
      <ClayBlob tone="fall" size="sm">
        <Icon className="size-4" aria-hidden />
      </ClayBlob>
      <div className="min-w-0 flex-1 space-y-1">
        <p className="font-semibold text-ink">{copy.title}</p>
        <p className="text-sm text-ink-muted">{message}</p>
        {copy.hint && <p className="text-xs text-ink-faint">{copy.hint}</p>}
      </div>
      {copy.retryable && (
        <ClayButton variant="soft" onClick={() => onRetry()} className="w-full sm:w-auto">
          <RefreshCw className="size-3.5" aria-hidden />
          Try again
        </ClayButton>
      )}
    </div>
  );
}
