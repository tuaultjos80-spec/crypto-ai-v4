"""Market data, indicators, and simulated-only trading helpers."""
import requests
import pandas as pd

COINS = {"BTC": ("bitcoin", "Bitcoin"), "ETH": ("ethereum", "Ethereum"), "SOL": ("solana", "Solana"), "ADA": ("cardano", "Cardano"), "XRP": ("ripple", "XRP")}
BASE = "https://api.coingecko.com/api/v3"
HEADERS = {"accept": "application/json", "User-Agent": "crypto-ai-v4-educational/1.0"}

def fetch_prices():
    ids = ",".join(v[0] for v in COINS.values())
    r = requests.get(f"{BASE}/simple/price", params={"ids": ids, "vs_currencies": "eur", "include_24hr_change": "true"}, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    result = {}
    for symbol, (coin_id, name) in COINS.items():
        item = data.get(coin_id, {})
        price = item.get("eur")
        if not isinstance(price, (int, float)) or price <= 0:
            raise ValueError(f"Prix indisponible : {symbol}")
        result[symbol] = {"name": name, "price": float(price), "change_24h": item.get("eur_24h_change")}
    return result

def fetch_history(symbol, days=90):
    coin_id = COINS[symbol][0]
    r = requests.get(f"{BASE}/coins/{coin_id}/market_chart", params={"vs_currency": "eur", "days": days}, headers=HEADERS, timeout=20)
    r.raise_for_status()
    data = r.json()["prices"]
    if len(data) < 40:
        raise ValueError("Historique insuffisant pour les indicateurs")
    frame = pd.DataFrame(data, columns=["timestamp", "price"])
    frame["date"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    return frame.set_index("date")["price"].resample("1D").last().dropna()

def indicators(prices):
    s = pd.Series(prices, dtype=float)
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = (100 - 100 / (1 + rs)).fillna(50)
    ema12 = s.ewm(span=12, adjust=False).mean()
    ema26 = s.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    return pd.DataFrame({"price": s, "sma10": s.rolling(10).mean(), "sma30": s.rolling(30).mean(), "rsi": rsi, "macd": macd, "macd_signal": macd_signal}, index=s.index)

def signal_from_indicators(row):
    if pd.isna(row["sma10"]) or pd.isna(row["sma30"]):
        return "ATTENDRE", "Historique insuffisant"
    if row["sma10"] > row["sma30"] and row["macd"] > row["macd_signal"] and row["rsi"] < 70:
        return "ACHETER", "Tendance et MACD haussiers, RSI sous 70"
    if row["sma10"] < row["sma30"] or row["rsi"] > 75:
        return "VENDRE", "Tendance baissière ou RSI élevé"
    return "CONSERVER", "Pas de signal confirmé"

def portfolio_value(cash, positions, prices):
    return cash + sum(qty * prices[symbol]["price"] for symbol, qty in positions.items())
