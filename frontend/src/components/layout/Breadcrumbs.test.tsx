import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test } from "vitest";
import Breadcrumbs from "./Breadcrumbs";

afterEach(() => cleanup());

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Breadcrumbs />
    </MemoryRouter>,
  );
}

test("a multi-segment trail links every ancestor except the current page", () => {
  renderAt("/stock/AVB#news");

  const stocksLink = screen.getByRole("link", { name: "Stocks" });
  expect(stocksLink.getAttribute("href")).toBe("/");
  const tickerLink = screen.getByRole("link", { name: "AVB" });
  expect(tickerLink.getAttribute("href")).toBe("/stock/AVB");

  const current = screen.getByText("News");
  expect(current.tagName).toBe("SPAN");
  expect(current.getAttribute("aria-current")).toBe("page");
});

test("a top-level page renders a single non-link crumb", () => {
  renderAt("/macro");

  const current = screen.getByText("Macro");
  expect(current.tagName).toBe("SPAN");
  expect(screen.queryByRole("link")).toBeNull();
});

test("the Stocks page itself renders with no separator", () => {
  const { container } = renderAt("/");

  expect(screen.getByText("Stocks")).toBeDefined();
  expect(container.querySelector("nav")?.textContent).toBe("Stocks");
});
