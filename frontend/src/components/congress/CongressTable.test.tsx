// specs/028-dashboard-tweaks-batch US4 (FR-012, FR-017, FR-018)
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test } from "vitest";
import type { CongressTrade } from "../../api/types";
import CongressTable from "./CongressTable";

afterEach(cleanup);

function trade(overrides: Partial<CongressTrade> = {}): CongressTrade {
  return {
    trade_id: "t1",
    chamber: "senate",
    person_id: "B001236",
    politician: "John Boozman",
    district: "AR",
    owner: "Joint",
    ticker: "AVGO",
    asset_description: "Broadcom Inc",
    asset_type: "Stock",
    transaction_type: "Purchase",
    amount_range: "$1,001 - $15,000",
    transaction_date: "2025-04-08",
    disclosure_date: "2026-08-20",
    link: null,
    ...overrides,
  };
}

function renderTable(trades: CongressTrade[]) {
  return render(
    <MemoryRouter>
      <CongressTable trades={trades} />
    </MemoryRouter>,
  );
}

test("a row with a ticker links to the singular /stock/<TICKER> route", () => {
  const { container } = renderTable([trade({ ticker: "AVGO" })]);
  expect(container.querySelector('a[href="/stock/AVGO"]')).toBeTruthy();
});

test("a null-ticker row renders no link element at all", () => {
  const { container } = renderTable([
    trade({ ticker: null, asset_description: "Some Municipal Bond Fund" }),
  ]);
  expect(container.querySelector("a")).toBeNull();
  expect(screen.getByText(/Some Municipal Bond Fund/)).toBeTruthy();
});

test("both transaction date and disclosure date are shown", () => {
  renderTable([trade({ transaction_date: "2025-04-08", disclosure_date: "2026-08-20" })]);
  expect(screen.getByText(/2025-04-08/)).toBeTruthy();
  expect(screen.getByText(/2026-08-20/)).toBeTruthy();
});

test("the amount range renders verbatim as text, never a computed number", () => {
  renderTable([trade({ amount_range: "$1,001 - $15,000" })]);
  expect(screen.getByText("$1,001 - $15,000")).toBeTruthy();
});

test("politician and chamber are shown", () => {
  renderTable([trade({ politician: "John Boozman", chamber: "senate" })]);
  expect(screen.getByText("John Boozman")).toBeTruthy();
  expect(screen.getByText(/senate/i)).toBeTruthy();
});
