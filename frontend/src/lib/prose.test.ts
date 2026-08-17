import { describe, expect, test } from "vitest";
import { emphasize, formatProse, splitSentences } from "./prose";

const plain = (text: string) => formatProse(text).blocks.map((b) => b.segments.map((s) => s.text).join(""));

describe("splitSentences", () => {
  test("splits on terminators", () => {
    expect(splitSentences("First one. Second one! Third one?")).toEqual([
      "First one.",
      "Second one!",
      "Third one?",
    ]);
  });

  test("does not split a decimal or a dollar amount", () => {
    expect(splitSentences("Support sits at 182.50 for now.")).toHaveLength(1);
    expect(splitSentences("It closed at $182.50 today.")).toHaveLength(1);
  });

  test("returns nothing for empty input", () => {
    expect(splitSentences("")).toEqual([]);
    expect(splitSentences("   ")).toEqual([]);
  });
});

describe("emphasize", () => {
  const marked = (s: string) =>
    emphasize(s).filter((seg) => seg.emphasis).map((seg) => seg.text);

  test("marks dollar amounts, percentages and bare price levels", () => {
    expect(marked("It fell 12.5% from $210.00 to 184.25")).toEqual(
      expect.arrayContaining(["12.5%", "$210.00", "184.25"]),
    );
  });

  test("marks direction vocabulary and tickers", () => {
    const hits = marked("AAPL looks bullish above resistance");
    expect(hits).toContain("AAPL");
    expect(hits).toContain("bullish");
    expect(hits).toContain("resistance");
  });

  test("keeps the sentence intact when reassembled", () => {
    const sentence = "AAPL closed at $210.00, up 3.2% and bullish.";
    expect(emphasize(sentence).map((s) => s.text).join("")).toBe(sentence);
  });

  test("returns a single plain segment when nothing matches", () => {
    const segs = emphasize("the company filed its annual report");
    expect(segs).toEqual([{ text: "the company filed its annual report", emphasis: false }]);
  });

  test("does not double-split an overlapping dollar amount", () => {
    const segs = emphasize("closed at $182.50");
    expect(segs.filter((s) => s.emphasis).map((s) => s.text)).toEqual(["$182.50"]);
  });
});

describe("formatProse", () => {
  test("groups a short narrative into paragraphs of at most two sentences", () => {
    const result = formatProse("One thing happened. Two things happened. Three things happened.");
    expect(result.asBullets).toBe(false);
    expect(result.blocks).toHaveLength(2);
    expect(plain("One thing happened. Two things happened. Three things happened.")[0]).toBe(
      "One thing happened. Two things happened.",
    );
  });

  test("switches to bullets once there are four or more sentences", () => {
    const text = "Alpha happened. Beta happened. Gamma happened. Delta happened.";
    const result = formatProse(text);
    expect(result.asBullets).toBe(true);
    expect(result.blocks).toHaveLength(4);
  });

  test("no rendered block exceeds three sentences (SC-004)", () => {
    const long =
      "One. Two. Three. Four. Five. Six. Seven. Eight. Nine. Ten. Eleven. Twelve.";
    for (const block of plain(long)) {
      const terminators = block.match(/[.!?](\s|$)/g) ?? [];
      expect(terminators.length).toBeLessThanOrEqual(3);
    }
  });

  test("empty text yields no blocks", () => {
    expect(formatProse("").blocks).toEqual([]);
    expect(formatProse("   ").blocks).toEqual([]);
  });

  test("a single sentence stays a single block", () => {
    const result = formatProse("Only one sentence here.");
    expect(result.blocks).toHaveLength(1);
    expect(result.asBullets).toBe(false);
  });
});
