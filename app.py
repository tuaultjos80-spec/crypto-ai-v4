"""Crypto AI V4: educational crypto paper-trading dashboard; no real orders."""
import datetime as dt
import json
import pandas as pd
import streamlit as st
from engine import COINS, fetch_prices, fetch_history, indicators, signal_from_indicators, portfolio_value

st.set_page_config(page_title="Crypto AI V4", page_icon="📈", layout="wide")
st.title("📈 Crypto AI V4 — Laboratoire de trading virtuel")
st.warning("Argent 100 % fictif. Signaux basés sur des règles, pas une IA prédictive. Aucun ordre réel.")
st.caption("Cours CoinGecko indicatifs, susceptibles d'être retardés ou indisponibles. Les performances passées ne prédisent pas les résultats futurs.")
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
    st.session_state.positions = {s: 0.0 for s in COINS}
    st.session_state.trades = []

with st.sidebar:
    st.header("Paramètres")
    auto_amount = st.number_input("Budget maximal par achat automatique (€)", min_value=10.0, max_value=500.0, value=100.0, step=10.0)
    max_allocation = st.slider("Allocation maximale par crypto (%)", 5, 30, 20, 5) / 100
    st.caption("Le robot agit uniquement lorsque vous cliquez sur le bouton. Pas de tâche 24 h/24.")
    if st.button("🔄 Actualiser les cours"):
        cached_prices.clear()
        st.rerun()

try:
    prices = cached_prices()
except Exception as exc:
    st.error("Prix indisponibles. Réessaie plus tard (API publique / connexion).")
    st.caption(str(exc))
    st.stop()

value = portfolio_value(st.session_state.cash, st.session_state.positions, prices)
a, b, c = st.columns(3)
a.metric("Portefeuille virtuel", f"{value:,.2f} €")
b.metric("Liquidités virtuelles", f"{st.session_state.cash:,.2f} €")
c.metric("Performance virtuelle", f"{(value / START_CASH - 1) * 100:+.2f} %")
st.subheader("Marché crypto")
st.dataframe(pd.DataFrame([{"Crypto": s, "Nom": d["name"], "Prix (€)": d["price"], "Variation 24 h (%)": d["change_24h"]} for s, d in prices.items()]), hide_index=True, use_container_width=True)

st.subheader("Analyse technique")
symbol = st.selectbox("Crypto à analyser", list(COINS))
try:
    history = cached_history(symbol)
    analysis = indicators(history)
    latest = analysis.iloc[-1]
    decision, reason = signal_from_indicators(latest)
    st.line_chart(analysis[["price", "sma10", "sma30"]].rename(columns={"price": "Prix", "sma10": "SMA 10", "sma30": "SMA 30"}))
    st.write(f"**Signal : {decision}** — {reason}")
    st.write(f"RSI : {latest['rsi']:.1f} | MACD : {latest['macd']:.4f} | Signal MACD : {latest['macd_signal']:.4f}")
except Exception as exc:
    st.info("Analyse historique momentanément indisponible (quota API ou données insuffisantes).")
    st.caption(str(exc))


def trade(symbol, side, amount, source):
    price = prices[symbol]["price"]
    fee = amount * FEE
    if side == "ACHAT":
        if amount + fee > st.session_state.cash + 1e-8:
            return "Liquidités insuffisantes."
        st.session_state.cash -= amount + fee
        st.session_state.positions[symbol] += amount / price
    else:
        if amount / price > st.session_state.positions[symbol] + 1e-10:
            return "Position insuffisante."
        st.session_state.positions[symbol] -= amount / price
        st.session_state.cash += amount - fee
    st.session_state.trades.append({"Date UTC": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "Crypto": symbol, "Action": side, "Montant (€)": round(amount, 2), "Prix (€)": price, "Frais (€)": round(fee, 4), "Source": source})
    return None

st.subheader("Robot virtuel — exécution manuelle d'un cycle")
st.caption("Le robot évalue les 5 cryptos sur 90 jours d'historique et passe au maximum un ordre fictif par crypto et par clic. Il ne tourne pas en arrière-plan.")
if st.button("🤖 Analyser et simuler un cycle", type="primary"):
    notes = []
    for sym in COINS:
        try:
            series = cached_history(sym)
            row = indicators(series).iloc[-1]
            action, reason = signal_from_indicators(row)
            holding = st.session_state.positions[sym] * prices[sym]["price"]
            total = portfolio_value(st.session_state.cash, st.session_state.positions, prices)
            if action == "ACHETER" and holding < 0.01:
                amount = min(auto_amount, max(0.0, total * max_allocation - holding), st.session_state.cash / (1 + FEE))
                if amount >= 10:
                    error = trade(sym, "ACHAT", amount, "Robot virtuel")
                    notes.append(f"{sym} : achat fictif {amount:.2f} €" if error is None else f"{sym} : {error}")
                else:
                    notes.append(f"{sym} : fonds ou plafond insuffisants")
            elif action == "VENDRE" and holding >= 0.01:
                error = trade(sym, "VENTE", holding, "Robot virtuel")
                notes.append(f"{sym} : vente fictive {holding:.2f} €" if error is None else f"{sym} : {error}")
            else:
                notes.append(f"{sym} : {action.lower()} — aucun except Exception as exc:
    notes.append(f"{sym} : données indisponibles ({exc})")  ({type(exc).__name__})")
    st.session_state.last_cycle = notes
    st.rerun()
if "last_cycle" in st.session_state:
    st.write(" | ".join(st.session_state.last_cycle))

st.subheader("Transaction manuelle fictive")
with st.form("manual"):
    sym = st.selectbox("Cryptomonnaie", list(COINS), key="manual_coin")
    side = st.radio("Opération", ["ACHAT", "VENTE"], horizontal=True)
    amount = st.number_input("Montant (€)", min_value=1.0, value=100.0, step=10.0)
    submit = st.form_submit_button("Valider l'ordre virtuel")
if submit:
    error = trade(sym, side, amount, "Manuel")
    if error:
        st.error(error)
    else:
        st.rerun()

st.subheader("Positions")
st.dataframe(pd.DataFrame([{"Crypto": s, "Unités": q, "Valeur (€)": q * prices[s]["price"]} for s, q in st.session_state.positions.items()]), hide_index=True, use_container_width=True)
st.subheader("Historique des transactions")
if st.session_state.trades:
    st.dataframe(pd.DataFrame(st.session_state.trades).iloc[::-1], hide_index=True, use_container_width=True)
    st.download_button("Télécharger l'historique CSV", pd.DataFrame(st.session_state.trades).to_csv(index=False).encode("utf-8-sig"), "crypto-ai-v4-transactions.csv", "text/csv")
else:
    st.info("Aucune transaction virtuelle pour le moment.")

st.subheader("Sauvegarde du portefeuille")
backup = {"version": 4, "cash": st.session_state.cash, "positions": st.session_state.positions, "trades": st.session_state.trades}
st.download_button("💾 Sauvegarder (JSON)", json.dumps(backup, ensure_ascii=False, indent=2), "crypto-ai-v4-sauvegarde.json", "application/json")
restore = st.file_uploader("Restaurer une sauvegarde JSON", type="json")
if restore is not None and st.button("Restaurer ce portefeuille"):
    try:
        data = json.load(restore)
        cash = float(data["cash"])
        positions = data["positions"]
        trades = data["trades"]
        if not (0 <= cash <= 1e12 and isinstance(positions, dict) and set(positions) == set(COINS) and isinstance(trades, list)):
            raise ValueError("Format invalide")
        positions = {s: float(positions[s]) for s in COINS}
        if any(not (0 <= q <= 1e12) for q in positions.values()):
            raise ValueError("Position invalide")
        st.session_state.cash = cash
        st.session_state.positions = positions
        st.session_state.trades = trades
        st.session_state.pop("last_cycle", None)
        st.rerun()
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        st.error(f"Sauvegarde invalide : {exc}")

if st.button("Réinitialiser le portefeuille virtuel"):
    st.session_state.cash = START_CASH
    st.session_state.positions = {s: 0.0 for s in COINS}
    st.session_state.trades = []
    st.session_state.pop("last_cycle", None)
    st.rerun()
st.caption("Sauvegarde manuelle : les sessions Streamlit peuvent être effacées. Frais fictifs 0,1 %, sans spread, slippage ni impôts. Aucun conseil financier.")
