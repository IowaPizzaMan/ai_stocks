// jsdom has no ResizeObserver, which recharts' ResponsiveContainer constructs
// on mount — without this, rendering any chart component throws.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
