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
