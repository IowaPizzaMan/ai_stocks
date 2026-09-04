import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import type { ConvictionDetail } from "../../api/types";
import ConvictionRationale from "./ConvictionRationale";

afterEach(() => cleanup());

function detail(overrides: Partial<ConvictionDetail> = {}): ConvictionDetail {
  return {
    level: "high",
    rank: 3,
    computed_at: "2026-09-04T00:00:00Z",
    conditions: {
      strategies: {
        pass: true,
        calls: {
          the_strat: { call: "buy", why: "full TFC bullish; aligned setups: weekly revstrat" },
          accumulation: { call: "buy", why: "accumulation confirmed" },
          gap_analysis: { call: "buy", why: "down-gap score 3 — bullish reversal" },
        },
      },
      zscore: {
        pass: true,
        daily: { value: -1.84, p25: -1.12, in_bottom_quartile: true, sample: 232 },
        weekly: { value: -1.31, p25: -0.97, in_bottom_quartile: true, sample: 84 },
      },
      revenue: { pass: true, growth_yoy: 0.081, change_qoq: 0.014, yoy_growing: true, qoq_declining: false },
    },
    blockers: [],
    caveats: [],
    missing_inputs: [],
    ...overrides,
  };
}

test("a high rating shows all three conditions passing with no blockers", () => {
  render(<ConvictionRationale detail={detail()} />);

  expect(screen.getByText(/high conviction/i)).toBeDefined();
  expect(screen.getByText(/The Strat: buy/)).toBeDefined();
  expect(screen.getByText(/Accumulation: buy/)).toBeDefined();
  expect(screen.getByText(/Gap Analysis: buy/)).toBeDefined();
  expect(screen.getAllByText(/in its bottom quartile/i)).toHaveLength(2); // daily + weekly
});

test("a non-high rating names its blocker(s)", () => {
  const nonHigh = detail({
    level: "medium",
    rank: 2,
    conditions: {
      ...detail().conditions,
      strategies: {
        pass: false,
        calls: {
          the_strat: { call: "buy", why: "full TFC bullish" },
          accumulation: { call: "not-buy", why: "no accumulation signal" },
          gap_analysis: { call: "buy", why: "down-gap score 3" },
        },
      },
    },
    blockers: ["strategies not aligned: accumulation not calling buy"],
  });
  render(<ConvictionRationale detail={nonHigh} />);

  expect(screen.getByText(/strategies not aligned: accumulation not calling buy/)).toBeDefined();
  expect(screen.queryByText(/high conviction/i)).toBeNull();
  expect(screen.getByText(/Accumulation: not-buy/)).toBeDefined();
});

test("a missing_inputs case shows the missing-data note", () => {
  const missingCase = detail({
    level: "low",
    rank: 1,
    conditions: {
      ...detail().conditions,
      zscore: {
        pass: false,
        daily: { value: null, p25: null, in_bottom_quartile: null, sample: 40 },
        weekly: detail().conditions.zscore.weekly,
      },
    },
    blockers: ["insufficient daily price history for z-score quartile"],
    missing_inputs: ["zscore:daily"],
  });
  render(<ConvictionRationale detail={missingCase} />);

  expect(screen.getByText(/Not enough data for: zscore:daily/)).toBeDefined();
  expect(screen.getByText(/insufficient price history \(40 of the needed sample\)/)).toBeDefined();
});

test("a legacy document with no conviction_detail shows the not-yet-recomputed fallback", () => {
  render(<ConvictionRationale detail={undefined} />);

  expect(screen.getByText(/not yet recomputed/i)).toBeDefined();
});

test("caveats render without affecting the level shown", () => {
  const withCaveat = detail({
    caveats: ["market breadth timing is unfavorable (trim) — a timing headwind, not a rating blocker"],
  });
  render(<ConvictionRationale detail={withCaveat} />);

  expect(screen.getByText(/high conviction/i)).toBeDefined();
  expect(screen.getByText(/timing headwind/)).toBeDefined();
});
