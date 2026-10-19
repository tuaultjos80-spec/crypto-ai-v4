"""Crypto AI V4 — laboratoire de trading fictif, sans ordre réel."""
import datetime as dt
import json
import math

import pandas as pd
import streamlit as st
from engine import (
    COINS,
    fetch_prices,
    fetch_history,
    indicators,
    signal_from_indicators,
    portfolio_value,
)

st.set_page_config(page_title="Crypto AI V4", page_icon="📈", layout="wide")
st.title("📈 Crypto AI V4 — Laboratoire de trading virtuel")
st.warning("Argent 100 % fictif. Signaux fondés sur des règles, pas une IA prédictive. Aucun ordre réel.")
st.caption("Cours CoinGecko indicatifs, parfois retardés ou indisponibles. Les performances passées ne prédisent pas les résultats futurs.")

START_CASH = 10_000.0
FEE = 0.001


@st.cache_data(ttl=90, show_spinner=False)
def cached_prices():
    return fetch_prices()


@st.cache_data(ttl=1800, show_spinner=False)
def cached_history(symbol):
    return fetch_history(symbol, 90)


if "cash" not in st.session_state:
    st.session_state.cash = START_CASH
if "positions" not in st.session_state:
    st.session_state.positions = {symbol: 0.0 for symbol in COINS}
if "trades" not in st.session_state:
    st.session_state.trades = []

with st.sidebar:
    st.header("Paramètres du robot virtuel")
    auto_amount = st.number_input(
        "Budget maximal par achat fictif (€)",
        min_value=10.0, max_value=500.0, value=100.0, step=10.0,
    )
    max_allocation = st.slider(
        "Allocation maximale par crypto (%)", 5, 30, 20, 5
    ) / 100
    st.caption("Le robot agit uniquement quand tu appuies sur son bouton. Il ne fonctionne pas en arrière-plan.")
    if st.button("🔄 Actualiser les cours"):
        cached_prices.clear()
        st.rerun()

try:
    prices = cached_prices()
except Exception as exc:
    st.error("Impossible de récupérer les cours. Réessaie plus tard.")
    st.caption(f"Détail technique : {type(exc).__name__} — {exc}")
    st.stop()

value = portfolio_value(st.session_state.cash, st.session_state.positions, prices)
col1, col2, col3 = st.columns(3)
col1.metric("Portefeuille virtuel", f"{value:,.2f} €")
col2.metric("Liquidités virtuelles", f"{st.session_state.cash:,.2f} €")
col3.metric("Performance virtuelle", f"{(value / START_CASH - 1) * 100:+.2f} %")

st.subheader("Marché crypto")
market_rows = [
    {
        "Crypto": symbol,
        "Nom": data["name"],
        "Prix (€)": data["price"],
        "Variation 24 h (%)": data["change_24h"],
    }
    for symbol, data in prices.items()
]
st.dataframe(pd.DataFrame(market_rows), hide_index=True, use_container_width=True)

st.subheader("Analyse technique")
selected_symbol = st.selectbox("Crypto à analyser", list(COINS))
try:
    history = cached_history(selected_symbol)
    analysis = indicators(history)
    latest = analysis.iloc[-1]
    decision, reason = signal_from_indicators(latest)
    st.line_chart(
        analysis[["price", "sma10", "sma30"]].rename(
            columns={"price": "Prix", "sma10": "SMA 10", "sma30": "SMA 30"}
        )
    )
    st.write(f"**Signal : {decision}** — {reason}")
    st.write(
        f"RSI : {latest['rsi']:.1f} | "
        f"MACD : {latest['macd']:.4f} | "
        f"Signal MACD : {latest['macd_signal']:.4f}"
    )
except Exception as exc:
    st.info("Analyse historique momentanément indisponible.")
    st.caption(f"Détail technique : {type(exc).__name__} — {exc}")


def trade(symbol, side, amount, source):
    """Exécute une transaction fictive; retourne une erreur ou None."""
    price = prices[symbol]["price"]
    fee = amount * FEE
    if side == "ACHAT":
        if amount + fee > st.session_state.cash + 1e-8:
            return "Liquidités virtuelles insuffisantes (frais compris)."
        st.session_state.cash -= amount + fee
        st.session_state.positions[symbol] += amount / price
    elif side == "VENTE":
        quantity = amount / price
        if quantity > st.session_state.positions[symbol] + 1e-10:
            return "Position virtuelle insuffisante."
        st.session_state.positions[symbol] = max(
            0.0, st.session_state.positions[symbol] - quantity
        )
        st.session_state.cash += amount - fee
    else:
        return "Opération inconnue."

    st.session_state.trades.append({
        "Date UTC": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "Crypto": symbol,
        "Action": side,
        "Montant (€)": round(amount, 2),
        "Prix (€)": price,
        "Frais (€)": round(fee, 4),
        "Source": source,
    })
    return None


st.subheader("Robot virtuel — exécution manuelle d'un cycle")
st.caption(
    "Le robot évalue les cinq cryptomonnaies sur 90 jours d'historique et "
    "passe au maximum un ordre fictif par crypto et par clic. "
    "Il ne tourne pas en arrière-plan."
)
if st.button("🤖 Analyser et simuler un cycle", type="primary"):
    notes = []
    for symbol in COINS:
        try:
            series = cached_history(symbol)
            row = indicators(series).iloc[-1]
            action, reason = signal_from_indicators(row)
            holding = st.session_state.positions[symbol] * prices[symbol]["price"]
            total = portfolio_value(
                st.session_state.cash, st.session_state.positions, prices
            )

            if action == "ACHETER" and holding < 0.01:
                amount = min(
                    auto_amount,
                    max(0.0, total * max_allocation - holding),
                    st.session_state.cash / (1 + FEE),
                )
                if amount >= 10:
                    error = trade(symbol, "ACHAT", amount, "Robot virtuel")
                    if error is None:
                        notes.append(f"{symbol} : achat fictif {amount:.2f} €")
                    else:
                        notes.append(f"{symbol} : {error}")
                else:
                    notes.append(f"{symbol} : fonds ou plafond insuffisants")
            elif action == "VENDRE" and holding >= 0.01:
                error = trade(symbol, "VENTE", holding, "Robot virtuel")
                if error is None:
                    notes.append(f"{symbol} : vente fictive {holding:.2f} €")
                else:
                    notes.append(f"{symbol} : {error}")
            else:
                notes.append(f"{symbol} : {action.lower()} — aucun ordre")
        except Exception as exc:
            notes.append(
                f"{symbol} : données indisponibles "
                f"({type(exc).__name__} : {str(exc)})"
            )

    st.session_state.last_cycle = notes
    st.rerun()

if "last_cycle" in st.session_state:
    st.write(" | ".join(st.session_state.last_cycle))

st.subheader("Transaction manuelle fictive")
with st.form("manual"):
    manual_symbol = st.selectbox("Cryptomonnaie", list(COINS), key="manual_coin")
    side = st.radio("Opération", ["ACHAT", "VENTE"], horizontal=True)
    amount = st.number_input("Montant (€)", min_value=1.0, value=100.0, step=10.0)
    submitted = st.form_submit_button("Valider l'ordre virtuel")

if submitted:
    error = trade(manual_symbol, side, amount, "Manuel")
    if error:
        st.error(error)
    else:
        st.rerun()

st.subheader("Positions")
position_rows = [
    {
        "Crypto": symbol,
        "Unités": quantity,
        "Valeur (€)": quantity * prices[symbol]["price"],
    }
    for symbol, quantity in st.session_state.positions.items()
]
st.dataframe(pd.DataFrame(position_rows), hide_index=True, use_container_width=True)

st.subheader("Historique des transactions")
if st.session_state.trades:
    transactions = pd.DataFrame(st.session_state.trades)
    st.dataframe(transactions.iloc[::-1], hide_index=True, use_container_width=True)
    st.download_button(
        "Télécharger l'historique CSV",
        transactions.to_csv(index=False).encode("utf-8-sig"),
        file_name="crypto-ai-v4-transactions.csv",
        mime="text/csv",
    )
else:
    st.info("Aucune transaction virtuelle pour le moment.")

st.subheader("Sauvegarde du portefeuille")
backup = {
    "version": 4,
    "cash": st.session_state.cash,
    "positions": st.session_state.positions,
    "trades": st.session_state.trades,
}
st.download_button(
    "💾 Sauvegarder (JSON)",
    json.dumps(backup, ensure_ascii=False, indent=2),
    file_name="crypto-ai-v4-sauvegarde.json",
    mime="application/json",
)

restore = st.file_uploader("Restaurer une sauvegarde JSON", type="json")
if restore is not None and st.button("Restaurer ce portefeuille"):
    try:
        data = json.load(restore)
        cash = float(data["cash"])
        positions = data["positions"]
        trades = data["trades"]
        if not math.isfinite(cash) or not 0 <= cash <= 1e12:
            raise ValueError("Liquidités invalides")
        if not isinstance(positions, dict) or set(positions) != set(COINS):
            raise ValueError("Liste de cryptomonnaies invalide")
        if not isinstance(trades, list):
            raise ValueError("Historique invalide")
        validated_positions = {symbol: float(positions[symbol]) for symbol in COINS}
        if any(
            not math.isfinite(qty) or not 0 <= qty <= 1e12
            for qty in validated_positions.values()
        ):
            raise ValueError("Position invalide")
        st.session_state.cash = cash
        st.session_state.positions = validated_positions
        st.session_state.trades = trades
        st.session_state.pop("last_cycle", None)
        st.rerun()
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, OverflowError) as exc:
        st.error(f"Sauvegarde invalide : {exc}")

if st.button("Réinitialiser le portefeuille virtuel"):
    st.session_state.cash = START_CASH
    st.session_state.positions = {symbol: 0.0 for symbol in COINS}
    st.session_state.trades = []
    st.session_state.pop("last_cycle", None)
    st.rerun()

st.caption(
    "Sauvegarde manuelle : les sessions Streamlit peuvent être effacées. "
    "Frais fictifs de 0,1 %, sans spread, slippage ni impôts. "
    "Aucun conseil financier."
)
