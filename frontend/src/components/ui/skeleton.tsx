import { cn } from "@/lib/cn";

export function Skeleton({ className }: { readonly className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "animate-shimmer rounded-xl bg-[length:200%_100%] shadow-well",
        "bg-[linear-gradient(90deg,var(--well)_0%,color-mix(in_oklab,var(--well),var(--surface)_70%)_50%,var(--well)_100%)]",
        className,
      )}
    />
  );
}
