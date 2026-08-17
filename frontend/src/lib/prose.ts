// Spec: specs/021-stock-page-redesign US4 (FR-010)
// Turns LLM narrative paragraphs into scannable structure. Deterministic and
// applied at render time, so analyses stored before this feature get the same
// treatment without a re-pull.

export interface ProseSegment {
  text: string;
  emphasis: boolean;
}

export interface ProseBlock {
  segments: ProseSegment[];
}

export interface FormattedProseResult {
  blocks: ProseBlock[];
  /** Bullets read better once there are enough sentences to enumerate. */
  asBullets: boolean;
}

const BULLET_THRESHOLD = 4; // sentences
const SENTENCES_PER_PARAGRAPH = 2;

/** Terms worth spotting without reading the sentence around them. */
const DIRECTION_TERMS = [
  "bullish", "bearish", "neutral", "overbought", "oversold",
  "support", "resistance", "breakout", "breakdown", "reversal",
  "accumulation", "distribution", "divergence", "uptrend", "downtrend",
];

// Price levels ($12.34 or a bare decimal), percentages, and uppercase tickers.
const PATTERNS: RegExp[] = [
  /\$\d[\d,]*(?:\.\d+)?/g,
  /-?\d+(?:\.\d+)?%/g,
  /\b\d+\.\d{2}\b/g,
  /\b[A-Z]{2,5}\b/g,
  new RegExp(`\\b(?:${DIRECTION_TERMS.join("|")})\\b`, "gi"),
];

/** Splits on sentence terminators. The lookahead for a capital or opening
 * quote keeps decimals ("12.34") from ending a sentence early. */
export function splitSentences(text: string): string[] {
  if (!text || !text.trim()) return [];
  return text
    .split(/(?<=[.!?])\s+(?=["'(“]?[A-Z])/)
    .map((s) => s.trim())
    .filter(Boolean);
}

/** Marks the spans worth emphasizing, leaving the rest as plain text. */
export function emphasize(sentence: string): ProseSegment[] {
  const hits: { start: number; end: number }[] = [];
  for (const pattern of PATTERNS) {
    pattern.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = pattern.exec(sentence)) !== null) {
      if (m[0]) hits.push({ start: m.index, end: m.index + m[0].length });
    }
  }
  if (!hits.length) return [{ text: sentence, emphasis: false }];

  // Merge overlaps so "$12.34" isn't also split by the bare-decimal rule.
  hits.sort((a, b) => a.start - b.start);
  const merged: { start: number; end: number }[] = [];
  for (const h of hits) {
    const last = merged[merged.length - 1];
    if (last && h.start <= last.end) last.end = Math.max(last.end, h.end);
    else merged.push({ ...h });
  }

  const segments: ProseSegment[] = [];
  let cursor = 0;
  for (const { start, end } of merged) {
    if (start > cursor) segments.push({ text: sentence.slice(cursor, start), emphasis: false });
    segments.push({ text: sentence.slice(start, end), emphasis: true });
    cursor = end;
  }
  if (cursor < sentence.length) segments.push({ text: sentence.slice(cursor), emphasis: false });
  return segments;
}

/** Groups sentences into short blocks — bullets when there are enough of them,
 * otherwise paragraphs of at most two sentences (SC-004). */
export function formatProse(text: string): FormattedProseResult {
  const sentences = splitSentences(text);
  if (!sentences.length) return { blocks: [], asBullets: false };

  const asBullets = sentences.length >= BULLET_THRESHOLD;
  if (asBullets) {
    return { blocks: sentences.map((s) => ({ segments: emphasize(s) })), asBullets };
  }

  const blocks: ProseBlock[] = [];
  for (let i = 0; i < sentences.length; i += SENTENCES_PER_PARAGRAPH) {
    const chunk = sentences.slice(i, i + SENTENCES_PER_PARAGRAPH).join(" ");
    blocks.push({ segments: emphasize(chunk) });
  }
  return { blocks, asBullets };
}
