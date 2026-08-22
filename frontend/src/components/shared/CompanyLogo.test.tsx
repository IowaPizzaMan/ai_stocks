import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import CompanyLogo from "./CompanyLogo";

afterEach(cleanup);

test("null src renders the fallback immediately, no img element", () => {
  const { container } = render(<CompanyLogo ticker="AAPL" src={null} />);
  expect(container.querySelector("img")).toBe(null);
  expect(screen.getByText("AA")).toBeTruthy();
});

test("undefined src renders the fallback", () => {
  render(<CompanyLogo ticker="GOOGL" />);
  expect(screen.getByText("GO")).toBeTruthy();
});

test("valid src renders an img with the given source", () => {
  const { container } = render(
    <CompanyLogo ticker="AAPL" src="https://images.financialmodelingprep.com/symbol/AAPL.png" />,
  );
  const img = container.querySelector("img");
  expect(img).not.toBe(null);
  expect(img?.getAttribute("src")).toBe("https://images.financialmodelingprep.com/symbol/AAPL.png");
});

test("onError swaps the img for the fallback", () => {
  const { container } = render(<CompanyLogo ticker="AAPL" src="https://broken.example/aapl.png" />);
  const img = container.querySelector("img")!;
  fireEvent.error(img);
  expect(container.querySelector("img")).toBe(null);
  expect(screen.getByText("AA")).toBeTruthy();
});
