import { formatCountdown } from "@/lib/format";

interface CountdownRingProps {
  readonly secondsLeft: number;
  readonly totalSeconds: number;
  readonly size?: number;
}

/** Clay dial showing the time left in a rate-limit window. */
export function CountdownRing({ secondsLeft, totalSeconds, size = 76 }: CountdownRingProps) {
  const stroke = 6;
  const radius = (size - stroke) / 2 - 4;
  const circumference = 2 * Math.PI * radius;
  const progress = totalSeconds > 0 ? Math.min(1, secondsLeft / totalSeconds) : 0;

  return (
    <div
      className="relative grid shrink-0 place-items-center rounded-full bg-surface shadow-clay-sm"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="absolute inset-0 -rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" strokeWidth={stroke} className="stroke-well" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - progress)}
          className="stroke-caution transition-[stroke-dashoffset] duration-300 ease-linear"
        />
      </svg>
      <span className="relative font-mono text-sm font-semibold tabular-nums text-ink" role="timer" aria-live="off">
        {formatCountdown(secondsLeft)}
      </span>
    </div>
  );
}
