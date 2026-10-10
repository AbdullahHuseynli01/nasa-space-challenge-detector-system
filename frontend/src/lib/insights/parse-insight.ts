/**
 * Turns the backend's plain-text explanation into structured segments so the
 * UI can highlight the facts the model was instructed to state.
 */

type InsightTokenKind =
  | "text"
  | "number"
  | "direction"
  | "significant"
  | "not_significant"
  | "entity";

export interface InsightToken {
  readonly kind: InsightTokenKind;
  readonly text: string;
}

type InsightSignificance = "significant" | "not_significant" | "unknown";

export interface ParsedInsight {
  readonly sentences: readonly (readonly InsightToken[])[];
  readonly significance: InsightSignificance;
}

export interface InsightContext {
  /** Region / variable names to emphasise, e.g. "Arctic", "sea ice fraction". */
  readonly entities: readonly string[];
}

const NOT_SIGNIFICANT = String.raw`(?:not|no|non)[\s-]+(?:statistically\s+)?significant(?:\s+trend)?`;
const SIGNIFICANT = String.raw`(?:statistically\s+)?significant`;
const DIRECTION = String.raw`no_significant_trend|increas(?:ing|ed|e)|decreas(?:ing|ed|e)`;
const NUMBER = String.raw`(?<![\w.])[-−]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?`;

/** Named capture groups of the matcher, in the order they are tried. */
const MATCH_KINDS = [
  "not_significant",
  "direction",
  "significant",
  "entity",
  "number",
] as const satisfies readonly InsightTokenKind[];

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function buildMatcher(entities: readonly string[]): RegExp {
  const entityAlternation = [...entities]
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)
    .map((entity) => escapeRegExp(entity).replace(/[\s_-]+/g, String.raw`[\s_-]+`))
    .join("|");

  const groups = [
    `(?<not_significant>\\b${NOT_SIGNIFICANT}\\b)`,
    `(?<direction>\\b(?:${DIRECTION})\\b)`,
    `(?<significant>\\b${SIGNIFICANT}\\b)`,
    entityAlternation ? `(?<entity>\\b(?:${entityAlternation})\\b)` : null,
    `(?<number>${NUMBER})`,
  ].filter((group): group is string => group !== null);

  return new RegExp(groups.join("|"), "gi");
}

function tokenize(sentence: string, matcher: RegExp): InsightToken[] {
  const tokens: InsightToken[] = [];
  let cursor = 0;

  for (const match of sentence.matchAll(matcher)) {
    const index = match.index;
    if (index > cursor) tokens.push({ kind: "text", text: sentence.slice(cursor, index) });

    const kind = MATCH_KINDS.find((group) => match.groups?.[group] !== undefined) ?? "text";
    // The backend requires the literal direction id; render it as prose.
    const text = kind === "direction" ? match[0].replaceAll("_", " ") : match[0];
    tokens.push({ kind, text });
    cursor = index + match[0].length;
  }

  if (cursor < sentence.length) tokens.push({ kind: "text", text: sentence.slice(cursor) });
  return tokens;
}

export function parseInsight(raw: string, { entities }: InsightContext): ParsedInsight {
  const text = raw.trim().replace(/\s+/g, " ");
  const matcher = buildMatcher(entities);
  // Split after sentence punctuation followed by a capital, so "0.05." or
  // "p < 0.05" inside a sentence are never treated as boundaries.
  const sentences = text.split(/(?<=[.!?])\s+(?=[A-Z])/).map((s) => tokenize(s, matcher));

  const kinds = new Set(sentences.flat().map((token) => token.kind));
  const significance: InsightSignificance = kinds.has("not_significant")
    ? "not_significant"
    : kinds.has("significant")
      ? "significant"
      : "unknown";

  return { sentences, significance };
}
