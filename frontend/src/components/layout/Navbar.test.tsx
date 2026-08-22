// Spec: specs/029-company-profile-tweaks (US1, FR-001)
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test } from "vitest";
import Navbar from "./Navbar";

afterEach(cleanup);

test("renders a News link", () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <Navbar />
    </MemoryRouter>,
  );
  const link = screen.getByRole("link", { name: "News" });
  expect(link.getAttribute("href")).toBe("/news");
});

test("marks News active when on /news", () => {
  render(
    <MemoryRouter initialEntries={["/news"]}>
      <Navbar />
    </MemoryRouter>,
  );
  const link = screen.getByRole("link", { name: "News" });
  expect(link.className).toContain("text-white");
});

test("does not mark News active on other routes", () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <Navbar />
    </MemoryRouter>,
  );
  const link = screen.getByRole("link", { name: "News" });
  expect(link.className).not.toContain("text-white");
});
