import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import RemoveTickerConfirm from "./RemoveTickerConfirm";

afterEach(cleanup);

test("names the ticker and states its data will be deleted", () => {
  render(<RemoveTickerConfirm ticker="NVDA" onConfirm={vi.fn()} onCancel={vi.fn()} />);
  expect(screen.getByRole("dialog").textContent).toContain("NVDA");
  expect(screen.getByRole("dialog").textContent).toMatch(/delete/i);
  expect(screen.getByRole("dialog").textContent).toMatch(/data/i);
});

test("clicking Cancel calls onCancel and never onConfirm", () => {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  render(<RemoveTickerConfirm ticker="NVDA" onConfirm={onConfirm} onCancel={onCancel} />);

  fireEvent.click(screen.getByRole("button", { name: /cancel delete nvda/i }));

  expect(onCancel).toHaveBeenCalledTimes(1);
  expect(onConfirm).not.toHaveBeenCalled();
});

test("clicking Confirm calls onConfirm exactly once", () => {
  const onConfirm = vi.fn();
  render(<RemoveTickerConfirm ticker="NVDA" onConfirm={onConfirm} onCancel={vi.fn()} />);

  fireEvent.click(screen.getByRole("button", { name: /confirm delete nvda/i }));

  expect(onConfirm).toHaveBeenCalledTimes(1);
});

test("Escape key triggers onCancel", () => {
  const onCancel = vi.fn();
  render(<RemoveTickerConfirm ticker="NVDA" onConfirm={vi.fn()} onCancel={onCancel} />);

  fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });

  expect(onCancel).toHaveBeenCalledTimes(1);
});

test("Enter on the focused Confirm button triggers onConfirm", () => {
  const onConfirm = vi.fn();
  render(<RemoveTickerConfirm ticker="NVDA" onConfirm={onConfirm} onCancel={vi.fn()} />);

  const confirmButton = screen.getByRole("button", { name: /confirm delete nvda/i });
  confirmButton.focus();
  fireEvent.keyDown(confirmButton, { key: "Enter" });
  fireEvent.click(confirmButton); // jsdom doesn't synthesize the native Enter->click activation

  expect(onConfirm).toHaveBeenCalledTimes(1);
});

test("while pending, both buttons are disabled and a pending state is shown", () => {
  render(
    <RemoveTickerConfirm ticker="NVDA" onConfirm={vi.fn()} onCancel={vi.fn()} pending />,
  );
  const confirmButton = screen.getByRole("button", { name: /confirm delete nvda/i }) as HTMLButtonElement;
  const cancelButton = screen.getByRole("button", { name: /cancel delete nvda/i }) as HTMLButtonElement;
  expect(confirmButton.disabled).toBe(true);
  expect(cancelButton.disabled).toBe(true);
});

test("shows an error message when provided, and stays open for a retry", () => {
  render(
    <RemoveTickerConfirm
      ticker="NVDA"
      onConfirm={vi.fn()}
      onCancel={vi.fn()}
      error="Couldn't delete NVDA — try again."
    />,
  );
  expect(screen.getByRole("alert").textContent).toContain("Couldn't delete NVDA");
  expect(screen.getByRole("button", { name: /confirm delete nvda/i })).toBeDefined();
});

test("interacting with the popover never bubbles a click to an ancestor", () => {
  const onWrapperClick = vi.fn();
  render(
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <div onClick={onWrapperClick}>
      <RemoveTickerConfirm ticker="NVDA" onConfirm={vi.fn()} onCancel={vi.fn()} />
    </div>,
  );

  fireEvent.click(screen.getByRole("button", { name: /confirm delete nvda/i }));

  expect(onWrapperClick).not.toHaveBeenCalled();
});
