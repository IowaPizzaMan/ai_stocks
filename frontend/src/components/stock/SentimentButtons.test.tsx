// specs/028-dashboard-tweaks-batch US3 (FR-005, FR-006, FR-006a) — thumbs
// up/down next to the ticker; hidden entirely (not disabled) for a stock the
// system doesn't track.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { api } from "../../api/client";
import SentimentButtons from "./SentimentButtons";

vi.mock("../../api/client", () => ({
  api: { get: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderButtons(sentiment: "liked" | "disliked" | null = null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SentimentButtons ticker="AAPL" tracked sentiment={sentiment} />
    </QueryClientProvider>,
  );
}

describe("SentimentButtons", () => {
  test("renders nothing at all when the ticker is not tracked", () => {
    const client = new QueryClient();
    const { container } = render(
      <QueryClientProvider client={client}>
        <SentimentButtons ticker="ZZZZ" tracked={false} sentiment={null} />
      </QueryClientProvider>,
    );
    expect(container.textContent).toBe("");
    expect(container.querySelectorAll("button").length).toBe(0);
  });

  test("renders both controls, neither active, when tracked and untagged", () => {
    renderButtons(null);
    expect(screen.getByRole("button", { name: "Like AAPL" })).toHaveProperty("ariaPressed", "false");
    expect(screen.getByRole("button", { name: "Dislike AAPL" })).toHaveProperty("ariaPressed", "false");
  });

  test("shows the thumbs-up control active when liked", () => {
    renderButtons("liked");
    expect(screen.getByRole("button", { name: "Like AAPL" })).toHaveProperty("ariaPressed", "true");
    expect(screen.getByRole("button", { name: "Dislike AAPL" })).toHaveProperty("ariaPressed", "false");
  });

  test("shows the thumbs-down control active when disliked", () => {
    renderButtons("disliked");
    expect(screen.getByRole("button", { name: "Dislike AAPL" })).toHaveProperty("ariaPressed", "true");
  });

  test("clicking thumbs-up PUTs liked", async () => {
    vi.mocked(api.put).mockResolvedValue({ data: { ticker: "AAPL", sentiment: "liked" } });
    renderButtons(null);
    fireEvent.click(screen.getByRole("button", { name: "Like AAPL" }));
    await waitFor(() =>
      expect(api.put).toHaveBeenCalledWith("/stocks/AAPL/sentiment", { sentiment: "liked" }),
    );
  });

  test("clicking the active control again clears it", async () => {
    vi.mocked(api.put).mockResolvedValue({ data: { ticker: "AAPL", sentiment: null } });
    renderButtons("liked");
    fireEvent.click(screen.getByRole("button", { name: "Like AAPL" }));
    await waitFor(() =>
      expect(api.put).toHaveBeenCalledWith("/stocks/AAPL/sentiment", { sentiment: "liked" }),
    );
  });

  test("clicking thumbs-down while liked switches to disliked", async () => {
    vi.mocked(api.put).mockResolvedValue({ data: { ticker: "AAPL", sentiment: "disliked" } });
    renderButtons("liked");
    fireEvent.click(screen.getByRole("button", { name: "Dislike AAPL" }));
    await waitFor(() =>
      expect(api.put).toHaveBeenCalledWith("/stocks/AAPL/sentiment", { sentiment: "disliked" }),
    );
  });
});
