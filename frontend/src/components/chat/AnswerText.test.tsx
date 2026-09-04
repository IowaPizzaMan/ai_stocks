import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test } from "vitest";
import AnswerText from "./AnswerText";

afterEach(() => {
  cleanup();
});

test("plain single-sentence text renders as one paragraph (FR-006 baseline)", () => {
  const { container } = render(<AnswerText text="13 stocks matched: TPR, MO, AAPL" />);
  const paragraphs = container.querySelectorAll("p");
  expect(paragraphs).toHaveLength(1);
  expect(paragraphs[0].textContent).toBe("13 stocks matched: TPR, MO, AAPL");
});

test("a blank line between two lines renders as two separate paragraphs (FR-001)", () => {
  const { container } = render(<AnswerText text={"First paragraph.\n\nSecond paragraph."} />);
  const paragraphs = container.querySelectorAll("p");
  expect(paragraphs).toHaveLength(2);
  expect(paragraphs[0].textContent).toBe("First paragraph.");
  expect(paragraphs[1].textContent).toBe("Second paragraph.");
});

test("- item lines render as a <ul> with distinct <li> entries (FR-002)", () => {
  const { container } = render(<AnswerText text={"- one\n- two\n- three"} />);
  const list = container.querySelector("ul");
  expect(list).not.toBeNull();
  expect(list?.querySelectorAll(":scope > li")).toHaveLength(3);
});

test("1. item lines render as an <ol> with distinct <li> entries (FR-002)", () => {
  const { container } = render(<AnswerText text={"1. one\n2. two\n3. three"} />);
  const list = container.querySelector("ol");
  expect(list).not.toBeNull();
  expect(list?.querySelectorAll(":scope > li")).toHaveLength(3);
});

test("an indented nested list item renders as a nested list inside its parent <li> (FR-002)", () => {
  const { container } = render(
    <AnswerText text={"- parent one\n  - nested a\n  - nested b\n- parent two"} />,
  );
  const topList = container.querySelector("ul");
  expect(topList).not.toBeNull();
  const topItems = topList?.querySelectorAll(":scope > li") ?? [];
  expect(topItems).toHaveLength(2);
  const nestedList = topItems[0].querySelector("ul");
  expect(nestedList).not.toBeNull();
  expect(nestedList?.querySelectorAll(":scope > li")).toHaveLength(2);
});

test("a single \\n (no blank line) renders as a visible line break, not collapsed (FR-009)", () => {
  const { container } = render(<AnswerText text={"line one\nline two"} />);
  const paragraphs = container.querySelectorAll("p");
  expect(paragraphs).toHaveLength(1);
  expect(paragraphs[0].querySelector("br")).not.toBeNull();
  expect(paragraphs[0].textContent).toContain("line one");
  expect(paragraphs[0].textContent).toContain("line two");
});

test("**bold**/*italic* render as <strong>/<em> with no literal markup characters (FR-003)", () => {
  render(<AnswerText text="This is **bold** and this is *italic*." />);
  const strong = screen.getByText("bold");
  expect(strong.tagName).toBe("STRONG");
  const em = screen.getByText("italic");
  expect(em.tagName).toBe("EM");
  expect(screen.queryByText(/\*/)).toBeNull();
});

test("# Header through ###### Header render as <h1> through <h6> (FR-003)", () => {
  const text = [
    "# H1 text",
    "## H2 text",
    "### H3 text",
    "#### H4 text",
    "##### H5 text",
    "###### H6 text",
  ].join("\n\n");
  render(<AnswerText text={text} />);
  expect(screen.getByText("H1 text").tagName).toBe("H1");
  expect(screen.getByText("H2 text").tagName).toBe("H2");
  expect(screen.getByText("H3 text").tagName).toBe("H3");
  expect(screen.getByText("H4 text").tagName).toBe("H4");
  expect(screen.getByText("H5 text").tagName).toBe("H5");
  expect(screen.getByText("H6 text").tagName).toBe("H6");
});

test("`code` renders as <code> with no literal backticks (FR-003)", () => {
  render(<AnswerText text="Run `npm test` to check." />);
  const code = screen.getByText("npm test");
  expect(code.tagName).toBe("CODE");
  expect(screen.queryByText(/`/)).toBeNull();
});

test("> quote renders as <blockquote> with no literal > (FR-003)", () => {
  render(<AnswerText text="> a quoted line" />);
  const quote = screen.getByText("a quoted line");
  expect(quote.closest("blockquote")).not.toBeNull();
});

test("[text](url) renders as a clickable link with target/rel, including non-http schemes (FR-010)", () => {
  const { rerender } = render(<AnswerText text="[click here](https://example.com/path)" />);
  let link = screen.getByRole("link", { name: "click here" });
  expect(link.getAttribute("href")).toBe("https://example.com/path");
  expect(link.getAttribute("target")).toBe("_blank");
  expect(link.getAttribute("rel")).toBe("noopener noreferrer");

  rerender(<AnswerText text="[js link](javascript:alert(1))" />);
  link = screen.getByRole("link", { name: "js link" });
  expect(link.getAttribute("href")).toBe("javascript:alert(1)");
  expect(link.getAttribute("target")).toBe("_blank");
  expect(link.getAttribute("rel")).toBe("noopener noreferrer");
});

test("embedded <script> text renders as inert visible text, never executed (FR-004)", () => {
  const { container } = render(<AnswerText text="before <script>alert(1)</script> after" />);
  expect(container.querySelector("script")).toBeNull();
  expect(container.textContent).toContain("<script>alert(1)</script>");
});

test("an unclosed emphasis marker still renders fully and readably with no thrown error", () => {
  expect(() => render(<AnswerText text="This *is bold and never closes" />)).not.toThrow();
  expect(screen.getByText(/This/)).toBeDefined();
  expect(screen.getByText(/is bold and never closes/)).toBeDefined();
});

test("a root-relative link renders as in-app navigation, not a new-tab anchor (specs/035-chat-and-news-upgrade FR-013)", () => {
  render(
    <MemoryRouter>
      <AnswerText text="[NVDA](/stock/NVDA) rose 3% today." />
    </MemoryRouter>,
  );
  const link = screen.getByRole("link", { name: "NVDA" });
  expect(link.getAttribute("href")).toBe("/stock/NVDA");
  expect(link.getAttribute("target")).toBeNull();
  expect(link.getAttribute("rel")).toBeNull();
});

test("an absolute-URL link still opens in a new tab (specs/035-chat-and-news-upgrade — 034 behavior unchanged for external links)", () => {
  render(
    <MemoryRouter>
      <AnswerText text="[source](https://example.com/nvda) says so." />
    </MemoryRouter>,
  );
  const link = screen.getByRole("link", { name: "source" });
  expect(link.getAttribute("href")).toBe("https://example.com/nvda");
  expect(link.getAttribute("target")).toBe("_blank");
  expect(link.getAttribute("rel")).toBe("noopener noreferrer");
});

test("the rendered container carries word-wrap/overflow-safe classes for long unbroken content (FR-005)", () => {
  const longWord = "a".repeat(200);
  const { container } = render(<AnswerText text={longWord} />);
  const root = container.firstElementChild as HTMLElement;
  expect(root.className).toContain("break-words");
  expect(root.className).not.toContain("whitespace-nowrap");
});
