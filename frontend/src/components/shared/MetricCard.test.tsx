import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { formatMetric, getMetricBand } from "../../lib/constants";
import MetricCard from "./MetricCard";

afterEach(cleanup);

test("getMetricBand buckets low / mid / high values", () => {
  // priceToEarningsRatio range is 5–60
  expect(getMetricBand("priceToEarningsRatio", 6).text).toBe("text-sky-300"); // low end → ice blue
  expect(getMetricBand("priceToEarningsRatio", 32).text).toBe("text-zinc-300"); // mid → neutral
  expect(getMetricBand("priceToEarningsRatio", 58).text).toBe("text-red-400"); // high end → red
});

test("getMetricBand clamps values outside the range", () => {
  expect(getMetricBand("debtToEquityRatio", -5).text).toBe("text-sky-300");
  expect(getMetricBand("debtToEquityRatio", 99).text).toBe("text-red-400");
});

test("getMetricBand treats null as neutral", () => {
  expect(getMetricBand("grossProfitMargin", null).text).toBe("text-zinc-300");
});

test("formatMetric renders fractions as percents and ratios as multiples", () => {
  expect(formatMetric("grossProfitMargin", 0.463)).toBe("46.3%");
  expect(formatMetric("priceToEarningsRatio", 27.84)).toBe("27.8x");
  expect(formatMetric("freeCashFlowYield", null)).toBe("—");
});

test("MetricCard renders label, formatted value, and caption", () => {
  render(
    <MetricCard
      metricKey="returnOnEquity"
      label="ROE"
      value={1.51}
      caption="Elevated by buybacks shrinking equity"
    />,
  );
  expect(screen.getByText("ROE")).toBeDefined();
  expect(screen.getByText("151.0%")).toBeDefined();
  expect(screen.getByText(/Elevated by buybacks/)).toBeDefined();
});

test("MetricCard shows an em dash for missing values", () => {
  render(<MetricCard metricKey="freeCashFlowYield" label="FCF Yield" value={null} />);
  expect(screen.getByText("—")).toBeDefined();
});
