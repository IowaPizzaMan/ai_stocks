import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import type { CompanyProfile, OHLCVBar } from "../../api/types";
import CompanyProfileSection from "./CompanyProfileSection";

afterEach(cleanup);

function profile(overrides: Partial<CompanyProfile> = {}): CompanyProfile {
  return {
    ticker: "AAPL",
    name: "Apple Inc.",
    exchange: "NASDAQ",
    exchange_full: "NASDAQ Global Select",
    sector: "Technology",
    industry: "Consumer Electronics",
    country: "US",
    currency: "USD",
    website: "https://www.apple.com",
    ceo: "Timothy D. Cook",
    full_time_employees: 166000,
    ipo_date: "1980-12-12",
    description: "Apple Inc. is a global technology corporation.",
    logo_url: "https://images.financialmodelingprep.com/symbol/AAPL.png",
    market_cap: 4543533578600,
    beta: 1.086,
    last_dividend: 1.05,
    range_low: 224.69,
    range_high: 344.57,
    average_volume: 53759263,
    is_etf: false,
    is_fund: false,
    is_actively_trading: true,
    fetched_at: new Date().toISOString(),
    ...overrides,
  };
}

function bar(overrides: Partial<OHLCVBar>): OHLCVBar {
  return { date: "2026-08-20", open: 100, high: 101, low: 99, close: 100, volume: 1000, ...overrides };
}

test("renders identity and stat fields", () => {
  render(<CompanyProfileSection profile={profile()} isError={false} dailyBars={undefined} />);
  expect(screen.getByText("Apple Inc.")).toBeTruthy();
  expect(screen.getByText("NASDAQ")).toBeTruthy();
  expect(screen.getByText("Technology")).toBeTruthy();
  expect(screen.getByText("Consumer Electronics")).toBeTruthy();
  expect(screen.getByText("Timothy D. Cook")).toBeTruthy();
});

test("price/change/volume are computed from bars, not the profile", () => {
  const bars = [bar({ date: "2026-08-19", close: 300 }), bar({ date: "2026-08-20", close: 309.35, volume: 42216056 })];
  render(<CompanyProfileSection profile={profile()} isError={false} dailyBars={bars} />);

  expect(screen.getByText("$309.35")).toBeTruthy();
  expect(screen.getByText(/\+9\.35/)).toBeTruthy(); // computed change, not the profile's -1.95
  expect(screen.getByText("42,216,056")).toBeTruthy();
});

test("a single bar omits change without NaN", () => {
  const bars = [bar({ close: 309.35 })];
  render(<CompanyProfileSection profile={profile()} isError={false} dailyBars={bars} />);

  expect(screen.getByText("$309.35")).toBeTruthy();
  expect(screen.queryByText(/NaN/)).toBeNull();
});

test("ETF/fund omits CEO/employees/industry rows", () => {
  render(
    <CompanyProfileSection
      profile={profile({ is_etf: true, industry: null, ceo: null, full_time_employees: null })}
      isError={false}
      dailyBars={undefined}
    />,
  );
  expect(screen.queryByText("CEO")).toBeNull();
  expect(screen.queryByText("Employees")).toBeNull();
});

test("shows an unavailable state on error or missing profile", () => {
  render(<CompanyProfileSection profile={undefined} isError={true} dailyBars={undefined} />);
  expect(screen.getByText(/profile unavailable/i)).toBeTruthy();
});

test("shows an unavailable state when profile is undefined without an explicit error", () => {
  render(<CompanyProfileSection profile={undefined} isError={false} dailyBars={undefined} />);
  expect(screen.getByText(/profile unavailable/i)).toBeTruthy();
});
