import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import TabBar from "./TabBar";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const TABS = [
  { id: "one", label: "One" },
  { id: "two", label: "Two" },
];

test("renders one button per tab", () => {
  render(<TabBar tabs={TABS} activeTab="one" onSelect={vi.fn()} />);
  const buttons = screen.getAllByRole("button");
  expect(buttons.map((b) => b.textContent)).toEqual(["One", "Two"]);
});

test("applies the active style to the tab matching activeTab", () => {
  render(<TabBar tabs={TABS} activeTab="two" onSelect={vi.fn()} />);
  const active = screen.getByText("Two");
  const inactive = screen.getByText("One");
  expect(active.className).toContain("text-white");
  expect(inactive.className).not.toContain("text-white");
});

test("calls onSelect with the clicked tab's id", () => {
  const onSelect = vi.fn();
  render(<TabBar tabs={TABS} activeTab="one" onSelect={onSelect} />);
  screen.getByText("Two").click();
  expect(onSelect).toHaveBeenCalledWith("two");
});

test("renders optional trailing content", () => {
  render(
    <TabBar tabs={TABS} activeTab="one" onSelect={vi.fn()} trailing={<span>analyzed 2m ago</span>} />,
  );
  expect(screen.getByText("analyzed 2m ago")).toBeTruthy();
});

test("wraps buttons in a nav element", () => {
  render(<TabBar tabs={TABS} activeTab="one" onSelect={vi.fn()} />);
  expect(document.querySelectorAll("nav button").length).toBe(2);
});
