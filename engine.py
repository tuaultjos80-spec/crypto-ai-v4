"""Données de marché, indicateurs et outils de trading fictif uniquement."""
import pandas as pd
import requests
import streamlit as st

COINS = {
    "BTC": ("bitcoin", "Bitcoin"),
    "ETH": ("ethereum", "Ethereum"),
    "SOL": ("solana", "Solana"),
    "ADA": ("cardano", "Cardano"),
    "XRP": ("ripple", "XRP"),
}
BASE = "https://api.coingecko.com/api/v3"
HEADERS = {
    "accept": "application/json",
    "User-Agent": "crypto-ai-v4-educational/1.1",
}


def _get_json(path, params, timeout=20):
    try:
        response = requests.get(
            f"{BASE}{path}", params=params, headers=HEADERS, timeout=timeout
        )
        if response.status_code == 429:
            raise RuntimeError(
                "CoinGecko limite temporairement les requêtes (HTTP 429). "
                "Réessaie dans quelques minutes."
            )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout as exc:
        raise RuntimeError("CoinGecko ne répond pas à temps.") from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(f"Erreur de connexion CoinGecko : {exc}") from exc
    except ValueError as exc:
        raise RuntimeError("Réponse JSON CoinGecko invalide.") from exc


@st.cache_data(ttl=90, show_spinner=False)
def fetch_prices():
    ids = ",".join(coin_id for coin_id, _ in COINS.values())
    data = _get_json(
        "/simple/price",
        {"ids": ids, "vs_currencies": "eur", "include_24hr_change": "true"},
        timeout=15,
    )
    result = {}
    for symbol, (coin_id, name) in COINS.items():
        item = data.get(coin_id, {})
        price = item.get("eur")
        if not isinstance(price, (int, float)) or price <= 0:
            raise ValueError(f"Prix indisponible : {symbol}")
        result[symbol] = {
            "name": name,
            "price": float(price),
            "change_24h": item.get("eur_24h_change"),
        }
    return result


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_history(symbol, days=90):
    if symbol not in COINS:
        raise ValueError(f"Cryptomonnaie inconnue : {symbol}")
    if not isinstance(days, int) or days < 30:
        raise ValueError("La durée doit être un entier d'au moins 30 jours.")

    coin_id = COINS[symbol][0]
    payload = _get_json(
        f"/coins/{coin_id}/market_chart",
        {"vs_currency": "eur", "days": days},
    )
    values = payload.get("prices", [])
    if not isinstance(values, list) or len(values) < 40:
        raise ValueError(f"Historique insuffisant pour {symbol}.")

    frame = pd.DataFrame(values, columns=["timestamp", "price"])
    frame["timestamp"] = pd.to_numeric(frame["timestamp"], errors="coerce")
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame = frame.dropna(subset=["timestamp", "price"])
    frame = frame[frame["price"] > 0]
    frame["date"] = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    daily = frame.set_index("date")["price"].sort_index().resample("1D").last().dropna()
    if len(daily) < 40:
        raise ValueError(f"Moins de 40 jours de cours utilisables pour {symbol}.")
    return daily


def indicators(prices):
    s = pd.Series(prices, dtype=float)
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - 100 / (1 + rs)
    # Une série sans perte après la période initiale correspond à un RSI de 100.
    rsi = rsi.mask((loss == 0) & (gain > 0), 100)
    rsi = rsi.mask((loss == 0) & (gain == 0), 50)
    ema12 = s.ewm(span=12, adjust=False).mean()
    ema26 = s.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    return pd.DataFrame(
        {
            "price": s,
            "sma10": s.rolling(10).mean(),
            "sma30": s.rolling(30).mean(),
            "rsi": rsi,
            "macd": macd,
            "macd_signal": macd_signal,
        },
        index=s.index,
    )


def signal_from_indicators(row):
    fields = ["sma10", "sma30", "rsi", "macd", "macd_signal"]
    if any(pd.isna(row[field]) for field in fields):
        return "ATTENDRE", "Historique ou indicateurs insuffisants"
    if row["sma10"] > row["sma30"] and row["macd"] > row["macd_signal"] and row["rsi"] < 70:
        return "ACHETER", "Tendance et MACD haussiers, RSI sous 70"
    if row["sma10"] < row["sma30"] or row["rsi"] > 75:
        return "VENDRE", "Tendance baissière ou RSI élevé"
    return "CONSERVER", "Pas de signal confirmé"


def portfolio_value(cash, positions, prices):
    return cash + sum(qty * prices[symbol]["price"] for symbol, qty in positions.items())
