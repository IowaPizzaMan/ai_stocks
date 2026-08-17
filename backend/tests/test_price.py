"""Price endpoint tests — yfinance faked."""
import pandas as pd

from routers import price as price_router


def fake_history(rows=5):
    idx = pd.date_range("2026-07-01", periods=rows, freq="B")
    return pd.DataFrame(
        {"Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1_000_000},
        index=idx,
    )


def test_price_returns_bars_and_caches(client, db, monkeypatch):
    calls = []

    def fetch(ticker, period, interval):
        calls.append((ticker, period, interval))
        return fake_history()

    monkeypatch.setattr(price_router, "_fetch_history", fetch)

    r = client.get("/stocks/aapl/price").json()
    assert r["ticker"] == "AAPL"
    assert r["resolution"] == "daily"
    assert len(r["bars"]) == 5
    assert r["bars"][0] == {"date": "2026-07-01", "open": 100.0, "high": 101.0,
                            "low": 99.0, "close": 100.5, "volume": 1_000_000}
    assert calls == [("AAPL", "2y", "1d")]

    # second call served from cache
    client.get("/stocks/AAPL/price")
    assert len(calls) == 1

    # different resolution fetches fresh at weekly interval
    client.get("/stocks/AAPL/price?resolution=weekly")
    assert calls[-1] == ("AAPL", "5y", "1wk")


def test_price_unknown_resolution_422(client):
    assert client.get("/stocks/AAPL/price?resolution=hourly").status_code == 422


def test_price_empty_history_404(client, monkeypatch):
    monkeypatch.setattr(price_router, "_fetch_history",
                        lambda t, p, i: fake_history(0))
    assert client.get("/stocks/GONE/price").status_code == 404


def test_price_drops_nan_bars(client, monkeypatch):
    df = fake_history(3)
    df.iloc[1, df.columns.get_loc("Close")] = float("nan")
    monkeypatch.setattr(price_router, "_fetch_history", lambda t, p, i: df)

    r = client.get("/stocks/NAN/price")
    assert r.status_code == 200
    bars = r.json()["bars"]
    assert len(bars) == 2
    assert [b["date"] for b in bars] == ["2026-07-01", "2026-07-03"]


# --- 021-stock-page-redesign: yearly resolution -----------------------------


def daily_history(years: int, start="2006-01-02") -> pd.DataFrame:
    """Ascending daily bars whose close climbs by 1/day, so each resample bin's
    first/last/min/max are all predictable."""
    idx = pd.date_range(start, periods=years * 252, freq="B")
    n = len(idx)
    return pd.DataFrame(
        {
            "Open": [100.0 + i for i in range(n)],
            "High": [101.0 + i for i in range(n)],
            "Low": [99.0 + i for i in range(n)],
            "Close": [100.5 + i for i in range(n)],
            "Volume": [1_000] * n,
        },
        index=idx,
    )


def test_yearly_resolution_is_accepted_and_resamples_per_calendar_year(client, db, monkeypatch):
    monkeypatch.setattr(price_router, "_fetch_eod", lambda t, years=None: daily_history(3))

    r = client.get("/stocks/YR/price?resolution=yearly")
    assert r.status_code == 200
    bars = r.json()["bars"]

    # one bar per calendar year the daily data spans
    years = [b["date"][:4] for b in bars]
    assert years == sorted(set(years))
    assert len(bars) == len(set(years))

    # OHLCV aggregation: open=first, high=max, low=min, close=last, volume=sum
    first_year = bars[0]
    assert first_year["open"] == 100.0
    assert first_year["low"] == 99.0
    assert first_year["high"] > first_year["open"]
    assert first_year["close"] > first_year["open"]
    assert first_year["volume"] > 1_000


def test_yearly_caps_at_fifteen_years(client, db, monkeypatch):
    monkeypatch.setattr(price_router, "_fetch_eod", lambda t, years=None: daily_history(20))
    bars = client.get("/stocks/LONG/price?resolution=yearly").json()["bars"]
    assert 10 <= len(bars) <= 16  # 15y window, boundary year may partially land


def test_yearly_short_history_returns_all_available_without_error(client, db, monkeypatch):
    monkeypatch.setattr(price_router, "_fetch_eod",
                        lambda t, years=None: daily_history(2, start="2025-01-02"))
    r = client.get("/stocks/NEW/price?resolution=yearly")
    assert r.status_code == 200
    assert 1 <= len(r.json()["bars"]) <= 3


def test_monthly_window_is_three_years(client, db, monkeypatch):
    calls = []

    def fetch(ticker, period, interval):
        calls.append((ticker, period, interval))
        return fake_history()

    monkeypatch.setattr(price_router, "_fetch_history", fetch)
    client.get("/stocks/MO/price?resolution=monthly")
    assert calls[-1] == ("MO", "3y", "1mo")


def test_yearly_requests_deep_history_but_shorter_windows_do_not():
    """FMP's EOD endpoint returns only ~5 years unless `from` is supplied, which
    is not enough for the yearly panel's 10-15 candles (verified against the
    live API 2026-08-16). Shorter panels must not pay for the deeper fetch."""
    seen = []

    def fake_eod(ticker, years=None):
        seen.append(years)
        return daily_history(2)

    import routers.price as p
    original = p._fetch_eod
    p._fetch_eod = fake_eod
    try:
        p._fetch_history("AAPL", "15y", "1y")
        p._fetch_history("AAPL", "3y", "1mo")
        p._fetch_history("AAPL", "2y", "1d")
        p._fetch_history("AAPL", "5y", "1wk")
    finally:
        p._fetch_eod = original

    assert seen[0] == 15   # yearly asks for deep history
    assert seen[1] is None  # monthly/daily/weekly use the default window
    assert seen[2] is None
    assert seen[3] is None


def test_fetch_eod_adds_a_from_date_only_when_years_requested(monkeypatch):
    urls = []

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return []

    def fake_get(url, timeout=15):
        urls.append(url)
        return FakeResp()

    monkeypatch.setattr(price_router.requests, "get", fake_get)

    price_router._fetch_eod("AAPL")
    price_router._fetch_eod("AAPL", years=15)

    assert "&from=" not in urls[0]
    assert "&from=" in urls[1]
