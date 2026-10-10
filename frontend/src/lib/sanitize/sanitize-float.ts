/**
 * Float sanitisation for payloads sent to the Pydantic backend.
 *
 * Why 6 decimals: `JSON.stringify` switches to exponent notation for any
 * non-zero |x| < 1e-6 (`3.59e-12`), regardless of how the number was rounded.
 * Capping precision at 6 decimals guarantees every non-zero result has
 * |x| >= 1e-6, so the serialised payload is always plain fixed notation.
 */

const MAX_SAFE_DECIMALS = 6;

type RoundingMode =
  /** Round half away from zero. */
  | "round"
  /**
   * Truncate toward zero. Use this for values compared against a decimal
   * threshold (e.g. `p < 0.05`): truncation can never move a value across a
   * threshold expressible in `precision` decimals.
   */
  | "trunc";

export type SignConstraint = "positive" | "negative";

export interface SanitizeFloatOptions {
  /** Decimal places to keep, 0…6. Defaults to 6. */
  readonly precision?: number;
  readonly mode?: RoundingMode;
  /** Inclusive bounds; the result is clamped into [min, max]. */
  readonly min?: number;
  readonly max?: number;
  /**
   * Require a strictly signed result. If rounding would collapse the value to
   * 0, the smallest representable magnitude (10^-precision) is returned with
   * the required sign instead.
   */
  readonly sign?: SignConstraint;
}

export class SanitizeFloatError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SanitizeFloatError";
  }
}

export function sanitizeFloat(
  value: number,
  {
    precision = MAX_SAFE_DECIMALS,
    mode = "round",
    min = Number.NEGATIVE_INFINITY,
    max = Number.POSITIVE_INFINITY,
    sign,
  }: SanitizeFloatOptions = {},
): number {
  if (!Number.isFinite(value)) {
    throw new SanitizeFloatError(`Expected a finite number, received ${String(value)}.`);
  }
  if (!Number.isInteger(precision) || precision < 0 || precision > MAX_SAFE_DECIMALS) {
    throw new SanitizeFloatError(
      `precision must be an integer between 0 and ${MAX_SAFE_DECIMALS}.`,
    );
  }
  if (sign === "negative" && value > 0) {
    throw new SanitizeFloatError(`Expected a negative value, received ${value}.`);
  }
  if (sign === "positive" && value < 0) {
    throw new SanitizeFloatError(`Expected a positive value, received ${value}.`);
  }

  const factor = 10 ** precision;
  const magnitude = Math.abs(value);
  let scaled = mode === "trunc" ? truncScaled(magnitude, factor) : roundScaled(magnitude, precision);

  if (scaled === 0 && sign) scaled = 1;

  const signed = (Math.sign(value) || (sign === "negative" ? -1 : 1)) * (scaled / factor);
  const clamped = Math.min(max, Math.max(min, signed));

  // Normalise −0 to 0 so it serialises as "0".
  return clamped === 0 ? 0 : clamped;
}

/** trunc(magnitude * factor), corrected for binary under-estimation (0.57 * 1e6 = 569999.99…). */
function truncScaled(magnitude: number, factor: number): number {
  const truncated = Math.trunc(magnitude * factor);
  return (truncated + 1) / factor <= magnitude ? truncated + 1 : truncated;
}

/** Round half away from zero, using `toFixed` to avoid `x * factor` drift. */
function roundScaled(magnitude: number, precision: number): number {
  return Math.round(Number(magnitude.toFixed(precision)) * 10 ** precision);
}
