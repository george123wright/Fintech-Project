"""
Lens — Portfolio Intelligence
A Dash/Plotly portfolio analytics dashboard.

Install dependencies:
    pip install dash dash-bootstrap-components plotly pandas numpy

Run:
    python lens_portfolio.py
Then open http://127.0.0.1:8050 in your browser.
"""

import dash
from dash import dcc, html, Input, Output, State, ctx
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
import numpy as np
import pandas as pd


# ─────────────────────────────────────────────
# MOCK DATA
# ─────────────────────────────────────────────

HOLDINGS = [
    {"sym": "NVDA", "name": "NVIDIA Corporation",            "weight": 22.4, "price": 148.20, "unreal": 2140,  "real": 480,  "color": "#7b6ef6"},
    {"sym": "MSFT", "name": "Microsoft Corporation",         "weight": 19.1, "price": 415.30, "unreal": 1820,  "real": 0,    "color": "#5b8ef0"},
    {"sym": "AAPL", "name": "Apple Inc.",                    "weight": 16.8, "price": 189.50, "unreal": -310,  "real": 920,  "color": "#3dd68c"},
    {"sym": "TLT",  "name": "iShares 20+ Year Treasury ETF", "weight": 18.3, "price": 92.40,  "unreal": -640,  "real": 0,    "color": "#f0b959"},
    {"sym": "GLD",  "name": "SPDR Gold Shares ETF",          "weight": 12.1, "price": 198.70, "unreal": 390,   "real": 110,  "color": "#f05b5b"},
    {"sym": "BTC",  "name": "Bitcoin",                       "weight": 11.3, "price": 68420,  "unreal": 4200,  "real": -180, "color": "#e8a838"},
]

ALLOCATION = {
    "US Equities": 58.3,
    "Fixed Income": 18.3,
    "Commodities": 12.1,
    "Crypto": 11.3,
}
ALLOC_COLORS = ["#7b6ef6", "#f0b959", "#f05b5b", "#e8a838"]

CHART_DATA = {
    "NVDA": {
        "color": "#7b6ef6",
        "prices": [118, 121, 119, 123, 125, 122, 128, 131, 129, 135, 138, 133, 130, 136, 140, 138, 142, 145, 141, 139, 144, 148, 146, 150, 148],
        "events": [
            {"idx": 3,  "move": "+4.2%", "date": "Feb 14", "dir": "up",   "tag": "earnings",     "reason": "Q4 earnings beat — data centre revenue surged 409% YoY, crushing consensus. CEO guided H1 well above street expectations."},
            {"idx": 9,  "move": "+5.1%", "date": "Feb 20", "dir": "up",   "tag": "news",         "reason": "Microsoft expanded Azure AI deployment plans using NVDA chips as preferred infrastructure."},
            {"idx": 12, "move": "-3.8%", "date": "Feb 23", "dir": "down", "tag": "macro",        "reason": "A hotter CPI print pushed real yields higher and hit long-duration growth stocks."},
            {"idx": 17, "move": "+2.9%", "date": "Mar 01", "dir": "up",   "tag": "undetermined", "reason": None},
            {"idx": 22, "move": "+2.7%", "date": "Mar 07", "dir": "up",   "tag": "news",         "reason": "Semiconductor sentiment improved on a modest easing in export restriction expectations."},
        ],
    },
    "MSFT": {
        "color": "#5b8ef0",
        "prices": [398, 400, 402, 399, 403, 406, 404, 408, 410, 407, 412, 415, 413, 410, 414, 418, 416, 412, 415, 419, 417, 414, 418, 416, 415],
        "events": [
            {"idx": 5,  "move": "+2.1%", "date": "Feb 16", "dir": "up",   "tag": "earnings",     "reason": "Azure cloud guidance improved intra-quarter and Copilot monetisation came through faster than expected."},
            {"idx": 11, "move": "+2.0%", "date": "Feb 22", "dir": "up",   "tag": "news",         "reason": "The OpenAI partnership was extended with additional compute commitments."},
            {"idx": 13, "move": "-2.4%", "date": "Feb 24", "dir": "down", "tag": "macro",        "reason": "A Washington hearing on large AI partnerships raised antitrust questions around the ecosystem."},
            {"idx": 20, "move": "+1.4%", "date": "Mar 04", "dir": "up",   "tag": "undetermined", "reason": None},
        ],
    },
    "AAPL": {
        "color": "#3dd68c",
        "prices": [202, 200, 198, 201, 199, 196, 194, 197, 193, 190, 188, 191, 189, 186, 184, 188, 186, 183, 187, 189, 186, 184, 187, 190, 189],
        "events": [
            {"idx": 4,  "move": "-2.1%", "date": "Feb 15", "dir": "down", "tag": "news",         "reason": "China smartphone shipment commentary reinforced concerns around share losses to Huawei."},
            {"idx": 9,  "move": "-3.4%", "date": "Feb 20", "dir": "down", "tag": "macro",        "reason": "DMA-related regulatory headlines increased concerns over App Store monetisation pressure."},
            {"idx": 13, "move": "-2.8%", "date": "Feb 24", "dir": "down", "tag": "undetermined", "reason": None},
            {"idx": 19, "move": "+2.9%", "date": "Mar 03", "dir": "up",   "tag": "news",         "reason": "New AI feature announcements improved sentiment around the next device cycle."},
            {"idx": 23, "move": "+1.6%", "date": "Mar 08", "dir": "up",   "tag": "undetermined", "reason": None},
        ],
    },
    "TLT": {
        "color": "#f0b959",
        "prices": [95.0, 94.8, 94.6, 94.7, 94.3, 94.0, 93.8, 94.1, 93.9, 93.5, 93.2, 93.0, 92.9, 92.6, 92.3, 92.1, 92.4, 92.2, 92.0, 91.8, 92.1, 92.5, 92.8, 92.6, 92.4],
        "events": [
            {"idx": 4,  "move": "-0.9%", "date": "Feb 15", "dir": "down", "tag": "macro",        "reason": "Treasury yields moved higher as inflation data surprised to the upside."},
            {"idx": 10, "move": "-1.2%", "date": "Feb 22", "dir": "down", "tag": "macro",        "reason": "Markets pushed back rate-cut expectations and long-end duration sold off."},
            {"idx": 16, "move": "+0.7%", "date": "Mar 01", "dir": "up",   "tag": "news",         "reason": "A softer labour market print sparked a brief bid for duration assets."},
            {"idx": 22, "move": "+0.8%", "date": "Mar 07", "dir": "up",   "tag": "undetermined", "reason": None},
        ],
    },
    "GLD": {
        "color": "#f05b5b",
        "prices": [191, 192, 191.5, 192.4, 193.1, 194.3, 193.9, 194.8, 195.7, 196.2, 195.4, 196.6, 197.1, 196.8, 197.6, 198.4, 199.1, 198.7, 199.4, 200.1, 199.6, 198.9, 199.2, 199.0, 198.7],
        "events": [
            {"idx": 5,  "move": "+1.4%", "date": "Feb 16", "dir": "up",   "tag": "macro",        "reason": "Geopolitical stress increased demand for hedges and reserve assets."},
            {"idx": 11, "move": "+1.0%", "date": "Feb 22", "dir": "up",   "tag": "news",         "reason": "Central-bank reserve demand commentary supported precious metals."},
            {"idx": 18, "move": "+0.9%", "date": "Mar 04", "dir": "up",   "tag": "macro",        "reason": "Falling real yields improved the carry-adjusted case for gold."},
            {"idx": 22, "move": "-0.6%", "date": "Mar 07", "dir": "down", "tag": "undetermined", "reason": None},
        ],
    },
    "BTC": {
        "color": "#e8a838",
        "prices": [61200, 62400, 61800, 63200, 64500, 65300, 64800, 66100, 67200, 66800, 68100, 69400, 68800, 67600, 68400, 70100, 69500, 68700, 69900, 70800, 70000, 69100, 69800, 69000, 68420],
        "events": [
            {"idx": 3,  "move": "+3.6%", "date": "Feb 14", "dir": "up",   "tag": "news",         "reason": "ETF-related flow commentary supported broader crypto risk appetite."},
            {"idx": 11, "move": "+4.2%", "date": "Feb 22", "dir": "up",   "tag": "macro",        "reason": "A weaker dollar and improving liquidity expectations lifted high-beta alternatives."},
            {"idx": 17, "move": "-2.1%", "date": "Mar 01", "dir": "down", "tag": "macro",        "reason": "Real-yield strength triggered profit-taking across speculative assets."},
            {"idx": 23, "move": "-1.1%", "date": "Mar 08", "dir": "down", "tag": "undetermined", "reason": None},
        ],
    },
}

STOCK_DETAIL = {
    "NVDA": {
        "consensus": "BUY", "buy": 32, "hold": 8, "sell": 2,
        "avg_target": 178.50, "current": 148.20, "day_move": "+2.3% today",
        "coverage": [("Morgan Stanley", "$185", "OW"), ("Goldman Sachs", "$180", "Buy"), ("JP Morgan", "$175", "OW"), ("UBS", "$155", "Neutral")],
        "var_1d": "-3.2%", "cvar": "-4.8%", "beta": "1.74", "sharpe": "1.86", "max_dd": "-28.4%", "vol": "48.2%",
        "factors": [("Growth", 0.92), ("Momentum", 0.78), ("Quality", 0.65), ("Rate Sensitivity", -0.58), ("Value", -0.12)],
        "pe": "68.4x", "fwd_pe": "35.1x", "ev_ebitda": "52.3x", "peg": "0.54",
        "dcf": "$138–$165", "rev_growth": "+82%", "eps_growth": "+103%",
        "sector": "Semiconductors", "geography": "US (98%)", "revenue_exposure": "China 21%", "currency_risk": "USD", "corr_spx": "0.82",
        "insight_analyst": "Analyst consensus is strongly bullish with material upside to target. Conviction is driven by AI infrastructure demand, but the valuation already assumes exceptional execution.",
        "insight_risk": "NVDA carries the highest standalone risk in the portfolio. At 22.4% weight it is the single largest contributor to total volatility and remains sensitive to real-yield shocks.",
        "insight_exposure": "NVDA is a concentrated growth and momentum exposure. Combined with MSFT and AAPL, it makes the portfolio far more duration-sensitive than the ticker count suggests.",
        "insight_valuation": "The PEG ratio still looks supportive, but most of the AI narrative is already capitalised into the multiple. The main risk is compression if growth slows even modestly.",
    },
    "MSFT": {
        "consensus": "BUY", "buy": 28, "hold": 10, "sell": 1,
        "avg_target": 452.00, "current": 415.30, "day_move": "+0.9% today",
        "coverage": [("Barclays", "$470", "OW"), ("BofA", "$455", "Buy"), ("Citi", "$445", "Buy"), ("Jefferies", "$420", "Hold")],
        "var_1d": "-2.1%", "cvar": "-3.1%", "beta": "1.18", "sharpe": "1.74", "max_dd": "-19.2%", "vol": "27.5%",
        "factors": [("Growth", 0.76), ("Momentum", 0.58), ("Quality", 0.88), ("Rate Sensitivity", -0.34), ("Value", 0.05)],
        "pe": "34.8x", "fwd_pe": "30.2x", "ev_ebitda": "24.9x", "peg": "1.48",
        "dcf": "$400–$446", "rev_growth": "+14%", "eps_growth": "+18%",
        "sector": "Software & Cloud", "geography": "Global", "revenue_exposure": "Enterprise / Cloud", "currency_risk": "USD", "corr_spx": "0.76",
        "insight_analyst": "Microsoft has a strong quality-growth profile with broad analyst support. Unlike NVDA, the debate is less about demand credibility and more about how much AI upside is already reflected in the multiple.",
        "insight_risk": "Risk is lower than NVDA, but MSFT still acts like a growth-duration asset. It softens the portfolio’s idiosyncratic risk while keeping meaningful exposure to AI sentiment and rates.",
        "insight_exposure": "MSFT diversifies the portfolio at the business-model level more than at the factor level. It still loads positively on growth and negatively on rising real yields.",
        "insight_valuation": "The valuation is premium but easier to defend because margins, cash generation and balance-sheet quality remain best-in-class. Upside is steadier, but probably less explosive than NVDA.",
    },
    "AAPL": {
        "consensus": "HOLD", "buy": 18, "hold": 17, "sell": 4,
        "avg_target": 198.00, "current": 189.50, "day_move": "-0.4% today",
        "coverage": [("Wells Fargo", "$205", "OW"), ("UBS", "$190", "Neutral"), ("Bernstein", "$185", "Market Perform"), ("Evercore", "$210", "OW")],
        "var_1d": "-1.8%", "cvar": "-2.7%", "beta": "1.05", "sharpe": "1.24", "max_dd": "-16.8%", "vol": "23.1%",
        "factors": [("Growth", 0.41), ("Momentum", -0.08), ("Quality", 0.84), ("Rate Sensitivity", -0.22), ("Value", 0.11)],
        "pe": "29.7x", "fwd_pe": "27.1x", "ev_ebitda": "21.8x", "peg": "2.05",
        "dcf": "$176–$202", "rev_growth": "+6%", "eps_growth": "+9%",
        "sector": "Consumer Technology", "geography": "Global", "revenue_exposure": "China 19%", "currency_risk": "USD", "corr_spx": "0.72",
        "insight_analyst": "Apple is less consensus-loved than MSFT or NVDA because growth is slower and hardware-cycle debates keep returning. The name still commands a premium because of ecosystem durability and buyback support.",
        "insight_risk": "Apple is lower-volatility than your other mega-cap tech exposures, but it still adds to the same broad growth regime risk. China headlines remain the most important external shock channel.",
        "insight_exposure": "AAPL is more quality and platform exposure than pure AI beta, but it does not diversify the portfolio much at the macro factor level. It still behaves like a large-cap US duration asset in most selloffs.",
        "insight_valuation": "The multiple looks full relative to medium-term growth. Unless a stronger device cycle emerges, rerating upside is modest and most of the case rests on resilience rather than acceleration.",
    },
    "TLT": {
        "consensus": "HOLD", "buy": 9, "hold": 15, "sell": 3,
        "avg_target": 96.50, "current": 92.40, "day_move": "+0.2% today",
        "coverage": [("Rates Strategy", "$97", "Overweight"), ("Macro Desk", "$95", "Neutral"), ("Cross-Asset", "$98", "Add"), ("PM Note", "$91", "Trim")],
        "var_1d": "-1.4%", "cvar": "-2.0%", "beta": "-0.24", "sharpe": "0.52", "max_dd": "-23.5%", "vol": "16.7%",
        "factors": [("Growth", -0.22), ("Momentum", -0.09), ("Quality", 0.18), ("Rate Sensitivity", 0.96), ("Value", 0.04)],
        "pe": "—", "fwd_pe": "—", "ev_ebitda": "—", "peg": "—",
        "dcf": "$94–$101", "rev_growth": "Yield-driven", "eps_growth": "Yield-driven",
        "sector": "Long Duration Treasuries", "geography": "US", "revenue_exposure": "None", "currency_risk": "USD duration", "corr_spx": "-0.28",
        "insight_analyst": "TLT is the main ballast asset in the portfolio, but it only helps when growth scares dominate inflation scares. Its role is macro hedging rather than alpha generation.",
        "insight_risk": "The ETF’s risk comes almost entirely from duration. A hawkish rates repricing can still create meaningful short-term drawdowns even though the asset is defensive in equity selloffs.",
        "insight_exposure": "TLT is your strongest positive exposure to falling yields. That makes it a useful offset to tech-duration risk, but not a perfect hedge when inflation is the shock driver.",
        "insight_valuation": "Valuation is effectively about the term premium and expected path of policy rates. If the market is too hawkish on cuts, TLT becomes more attractive; if inflation re-accelerates, fair value is lower.",
    },
    "GLD": {
        "consensus": "BUY", "buy": 14, "hold": 8, "sell": 1,
        "avg_target": 205.00, "current": 198.70, "day_move": "+0.5% today",
        "coverage": [("Metals Desk", "$207", "Buy"), ("Macro Strategy", "$204", "Accumulate"), ("Commodities PM", "$200", "Hold"), ("Private Bank", "$210", "Buy")],
        "var_1d": "-1.2%", "cvar": "-1.8%", "beta": "0.14", "sharpe": "0.88", "max_dd": "-12.6%", "vol": "14.4%",
        "factors": [("Growth", -0.11), ("Momentum", 0.17), ("Quality", 0.02), ("Rate Sensitivity", 0.54), ("Value", 0.08)],
        "pe": "—", "fwd_pe": "—", "ev_ebitda": "—", "peg": "—",
        "dcf": "$196–$212", "rev_growth": "Spot-price linked", "eps_growth": "Spot-price linked",
        "sector": "Gold / Commodities", "geography": "Global", "revenue_exposure": "None", "currency_risk": "USD / real yields", "corr_spx": "0.08",
        "insight_analyst": "Gold is typically held for resilience rather than analyst-upside narratives. The constructive case strengthens when real yields fall or geopolitical risk rises.",
        "insight_risk": "GLD is less volatile than equities or crypto, but it is still regime-sensitive. The main risk is a stronger dollar or higher real yields eroding the hedge appeal.",
        "insight_exposure": "GLD gives the portfolio a rare exposure that is not simply another growth bet. It diversifies equity and crypto risk better than the headline volatility suggests.",
        "insight_valuation": "There is no traditional earnings multiple anchor, so fair value is mostly a macro judgement around real rates, reserve demand and stress premia.",
    },
    "BTC": {
        "consensus": "BUY", "buy": 21, "hold": 9, "sell": 6,
        "avg_target": 76000.0, "current": 68420.0, "day_move": "-1.1% today",
        "coverage": [("Digital Assets Desk", "$78,000", "Buy"), ("Macro Crypto", "$74,000", "Accumulate"), ("Cross-Asset PM", "$68,000", "Hold"), ("Private Markets", "$80,000", "Buy")],
        "var_1d": "-4.5%", "cvar": "-6.9%", "beta": "2.08", "sharpe": "1.31", "max_dd": "-42.7%", "vol": "61.4%",
        "factors": [("Growth", 0.63), ("Momentum", 0.81), ("Quality", -0.15), ("Rate Sensitivity", -0.29), ("Value", -0.34)],
        "pe": "—", "fwd_pe": "—", "ev_ebitda": "—", "peg": "—",
        "dcf": "$60k–$79k", "rev_growth": "Network adoption", "eps_growth": "Network adoption",
        "sector": "Digital Asset", "geography": "Global", "revenue_exposure": "None", "currency_risk": "USD liquidity", "corr_spx": "0.44",
        "insight_analyst": "BTC brings the most upside convexity in the portfolio, but also the widest dispersion of outcomes. The case is more flow- and liquidity-driven than fundamentals in the equity sense.",
        "insight_risk": "Bitcoin is the portfolio’s largest tail-risk sleeve per euro invested. Position sizing matters much more here than target price precision.",
        "insight_exposure": "BTC diversifies single-name equity risk, but not necessarily macro liquidity risk. In tightening episodes it can fall alongside growth assets rather than hedge them.",
        "insight_valuation": "There is no single clean valuation anchor, so fair value is a regime range rather than a point estimate. Liquidity, flows and risk appetite dominate short-horizon pricing.",
    },
}

WATCHLIST_NOTES = {
    "NVDA": "Dominant AI capex beneficiary, but already heavily owned and rate-sensitive.",
    "MSFT": "Quality compounder with broad AI monetisation optionality.",
    "AAPL": "Platform strength remains intact, but growth expectations are lower.",
    "TLT": "Main duration hedge if growth weakens faster than inflation.",
    "GLD": "Useful macro diversifier when real yields or geopolitical stress shift.",
    "BTC": "High-convexity liquidity trade; powerful but position-size sensitive.",
}

RANGE_CONFIG = {
    "1M": 25,
    "3M": 65,
    "6M": 130,
    "1Y": 260,
}

DEFAULT_NAV = {
    "page": "overview",
    "sym": None,
    "chart_sym": "NVDA",
    "highlight_idx": None,
    "chart_range": "1M",
    "macro": "FOMC",
}

PORTFOLIO_VALUE = 47284.60
PORTFOLIO_PNL = 2766.20
PORTFOLIO_PNL_PCT = 6.2


# ─────────────────────────────────────────────
# STYLE CONSTANTS
# ─────────────────────────────────────────────

DARK = {"backgroundColor": "#0a0a0f", "color": "#e8e8f0"}
SURFACE = {"backgroundColor": "#111118", "color": "#e8e8f0"}
BORDER = "1px solid #1e1e2e"
MONO = "DM Mono, monospace"
ACCENT = "#7b6ef6"
MUTED = "#6b6b8a"
GREEN = "#3dd68c"
RED = "#f05b5b"
YELLOW = "#f0b959"


# ─────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────

def get_holding(sym):
    return next((h for h in HOLDINGS if h["sym"] == sym), None)


def format_price(value):
    return f"${value:,.2f}"


def format_change(pct, label):
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}% ({label})"


def consensus_color(consensus):
    mapping = {"BUY": GREEN, "HOLD": YELLOW, "SELL": RED}
    return mapping.get(consensus.upper(), ACCENT)


def expand_series(base_prices, target_len):
    base = np.asarray(base_prices, dtype=float)
    if target_len == len(base):
        return base

    base_x = np.linspace(0, 1, len(base))
    target_x = np.linspace(0, 1, target_len)
    interp = np.interp(target_x, base_x, base)

    amplitude = max(np.std(base) * 0.18, 0.15)
    wave = amplitude * np.sin(np.linspace(0, 8 * np.pi, target_len))
    series = interp + wave
    series[0] = base[0]
    series[-1] = base[-1]
    return series


def rescale_events(events, base_len, target_len):
    if base_len == target_len:
        return [dict(ev) for ev in events]

    out = []
    for ev in events:
        scaled_idx = int(round(ev["idx"] / (base_len - 1) * (target_len - 1)))
        new_ev = dict(ev)
        new_ev["idx"] = max(0, min(target_len - 1, scaled_idx))
        out.append(new_ev)
    return out


def get_chart_payload(sym, range_key="1M"):
    data = CHART_DATA[sym]
    base_prices = data["prices"]
    target_len = RANGE_CONFIG.get(range_key, RANGE_CONFIG["1M"])
    prices = expand_series(base_prices, target_len)
    dates = pd.bdate_range(end="2025-03-10", periods=target_len)
    events = rescale_events(data["events"], len(base_prices), target_len)
    return dates, prices, events


# ─────────────────────────────────────────────
# CHART BUILDERS
# ─────────────────────────────────────────────

def build_frontier_chart():
    stock_risk = [0.32, 0.19, 0.16, 0.11, 0.14, 0.40]
    stock_return = [0.18, 0.14, 0.12, 0.05, 0.09, 0.19]
    syms = [h["sym"] for h in HOLDINGS]
    colors = [h["color"] for h in HOLDINGS]

    sigmas = np.linspace(0.08, 0.43, 200)
    returns = 0.06 + 0.18 * np.sqrt(np.clip((sigmas - 0.08) / 0.35, 0, 1)) + 0.08 * ((sigmas - 0.08) / 0.35)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sigmas, y=returns, mode="lines",
        line=dict(color=ACCENT, width=2),
        name="Efficient Frontier", hoverinfo="skip"
    ))

    for i, sym in enumerate(syms):
        fig.add_trace(go.Scatter(
            x=[stock_risk[i]], y=[stock_return[i]],
            mode="markers+text",
            marker=dict(size=9, color=colors[i], line=dict(color=colors[i], width=1.5)),
            text=[sym], textposition="top right",
            textfont=dict(size=10, color=colors[i]),
            name=sym,
            hovertemplate=f"<b>{sym}</b><br>σ={stock_risk[i]:.0%}  E(R)={stock_return[i]:.0%}<extra></extra>",
        ))

    fig.add_trace(go.Scatter(
        x=[0.21], y=[0.135],
        mode="markers+text",
        marker=dict(size=14, color=ACCENT, symbol="circle", line=dict(color="#e8e8f0", width=2)),
        text=["Portfolio"], textposition="top right",
        textfont=dict(size=11, color="#e8e8f0"),
        name="Your Portfolio",
        hovertemplate="<b>Your Portfolio</b><br>σ=21%  E(R)=13.5%<extra></extra>",
    ))

    fig.update_layout(
        plot_bgcolor="#0a0a0f", paper_bgcolor="#0a0a0f",
        font=dict(family="monospace", color=MUTED, size=10),
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(title="Risk (σ)", gridcolor="#1e1e2e", showline=False, zeroline=False, tickformat=".0%"),
        yaxis=dict(title="E(R)", gridcolor="#1e1e2e", showline=False, zeroline=False, tickformat=".0%"),
        showlegend=False,
        height=260,
    )
    return fig


def build_donut_chart():
    labels = list(ALLOCATION.keys())
    values = list(ALLOCATION.values())
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.62,
        marker=dict(colors=ALLOC_COLORS, line=dict(color="#111118", width=3)),
        textinfo="none",
        hovertemplate="<b>%{label}</b><br>%{value}%<extra></extra>",
    ))
    fig.update_layout(
        plot_bgcolor="#111118", paper_bgcolor="#111118",
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        height=200,
        annotations=[dict(text="€47.2k", x=0.5, y=0.5, font=dict(size=14, color="#e8e8f0", family="sans-serif"), showarrow=False)],
    )
    return fig


def build_price_chart(sym, highlight_idx=None, range_key="1M"):
    data = CHART_DATA.get(sym)
    if not data:
        return go.Figure()

    dates, prices, events = get_chart_payload(sym, range_key)
    color = data["color"]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=prices,
        fill="tozeroy",
        fillcolor=color + "18",
        line=dict(color=color, width=2),
        mode="lines",
        hovertemplate="<b>%{x|%b %d}</b>  $%{y:.2f}<extra></extra>",
        name=sym,
    ))

    for i, ev in enumerate(events):
        is_active = highlight_idx == i
        is_up = ev["dir"] == "up"
        arrow_color = GREEN if is_up else RED
        label = ev["move"] if ev["tag"] != "undetermined" else "?"
        ay = -40 if is_up else 40
        opacity = 1.0 if (highlight_idx is None or is_active) else 0.3

        fig.add_annotation(
            x=dates[ev["idx"]], y=prices[ev["idx"]],
            text=f"<b>{label}</b>",
            showarrow=True,
            arrowhead=2,
            arrowcolor=arrow_color,
            arrowwidth=2 if is_active else 1.5,
            ax=0, ay=ay,
            font=dict(size=10, color=arrow_color, family="monospace"),
            bgcolor=arrow_color + ("22" if is_active else "11"),
            bordercolor=arrow_color,
            borderwidth=1,
            opacity=opacity,
        )

    fig.update_layout(
        plot_bgcolor="#0a0a0f", paper_bgcolor="#0a0a0f",
        font=dict(family="monospace", color=MUTED, size=10),
        margin=dict(l=50, r=20, t=20, b=40),
        xaxis=dict(gridcolor="#1a1a28", showline=False, zeroline=False),
        yaxis=dict(gridcolor="#1a1a28", showline=False, zeroline=False, tickprefix="$"),
        showlegend=False,
        height=420,
    )
    return fig


# ─────────────────────────────────────────────
# LAYOUT HELPERS
# ─────────────────────────────────────────────

def section_kicker(text, margin_bottom="12px"):
    return html.Div(
        text,
        style={
            "fontSize": "10px",
            "letterSpacing": "0.12em",
            "textTransform": "uppercase",
            "color": MUTED,
            "marginBottom": margin_bottom,
        },
    )


def metric_card(label, value, color=None):
    return html.Div([
        html.Div(label, style={"fontSize": "10px", "color": MUTED, "letterSpacing": "0.08em", "textTransform": "uppercase", "marginBottom": "4px"}),
        html.Div(value, style={"fontSize": "15px", "fontWeight": "500", "color": color or "#e8e8f0"}),
    ], style={"textAlign": "right"})


def risk_card(label, value, sub, color):
    return html.Div([
        html.Div(label, style={"fontSize": "9px", "color": MUTED, "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "6px"}),
        html.Div(value, style={"fontSize": "16px", "fontWeight": "500", "color": color}),
        html.Div(sub, style={"fontSize": "10px", "color": MUTED, "marginTop": "3px"}),
    ], style={"backgroundColor": "#0a0a0f", "border": BORDER, "borderRadius": "6px", "padding": "12px"})


def insight_box(text):
    return html.Div([
        html.Span("◈ ", style={"color": ACCENT}),
        html.Span("Lens Analysis — ", style={"color": ACCENT, "fontWeight": "500"}),
        html.Span(text, style={"opacity": "0.9"}),
    ], style={
        "background": "linear-gradient(135deg, rgba(123,110,246,0.07), rgba(91,142,240,0.04))",
        "border": "1px solid rgba(123,110,246,0.2)",
        "borderRadius": "8px",
        "padding": "16px 18px",
        "fontSize": "12px",
        "lineHeight": "1.7",
        "color": "#e8e8f0",
        "gridColumn": "1 / -1",
        "marginTop": "4px",
    })


def nav_button(label, page, active=False):
    return html.Button(
        label,
        id={"type": "nav-btn", "page": page},
        n_clicks=0,
        style={
            "background": "none",
            "border": "none",
            "padding": 0,
            "color": ACCENT if active else MUTED,
            "fontSize": "12px",
            "marginRight": "24px" if page != "reports" else "0",
            "cursor": "pointer",
            "fontFamily": MONO,
        },
    )


def render_nav(state):
    current_page = state.get("page", "overview")
    return html.Nav([
        html.Button(
            [html.Span("lens"), html.Span(".", style={"color": ACCENT})],
            id={"type": "nav-btn", "page": "overview"},
            n_clicks=0,
            style={
                "background": "none",
                "border": "none",
                "padding": 0,
                "fontFamily": "sans-serif",
                "fontWeight": "800",
                "fontSize": "20px",
                "letterSpacing": "-0.5px",
                "color": "#e8e8f0",
                "cursor": "pointer",
            },
        ),
        html.Div([
            nav_button("Overview", "overview", current_page == "overview"),
            nav_button("Watchlist", "watchlist", current_page == "watchlist"),
            nav_button("Scenarios", "scenarios", current_page == "scenarios" or current_page == "macro"),
            nav_button("Reports", "reports", current_page == "reports"),
        ]),
        html.Button(
            "⚡ FOMC · 5 days",
            id={"type": "macro-link", "event": "FOMC"},
            n_clicks=0,
            style={
                "background": "rgba(240,185,89,0.1)",
                "border": "1px solid rgba(240,185,89,0.25)",
                "color": YELLOW,
                "padding": "5px 12px",
                "borderRadius": "20px",
                "fontSize": "11px",
                "cursor": "pointer",
                "fontFamily": MONO,
            },
        ),
    ], style={
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "space-between",
        "padding": "18px 32px",
        "borderBottom": BORDER,
        "backgroundColor": "rgba(10,10,15,0.97)",
        "position": "sticky",
        "top": "0",
        "zIndex": "100",
        "fontFamily": MONO,
    })


def holdings_table():
    rows = []
    for h in HOLDINGS:
        unreal_color = GREEN if h["unreal"] >= 0 else RED
        real_color = GREEN if h["real"] > 0 else (MUTED if h["real"] == 0 else RED)
        rows.append(
            html.Tr([
                html.Td([
                    html.Div([
                        html.Span("● ", style={"color": h["color"], "fontSize": "10px"}),
                        html.Span(h["sym"], style={"fontWeight": "500", "fontSize": "14px"}),
                    ]),
                    html.Div(h["name"], style={"fontSize": "11px", "color": MUTED, "marginTop": "2px"}),
                ]),
                html.Td(f"{h['weight']}%", style={"textAlign": "right", "color": MUTED}),
                html.Td(format_price(h["price"]), style={"textAlign": "right"}),
                html.Td(f"{'+' if h['unreal'] >= 0 else ''}€{h['unreal']:,}", style={"textAlign": "right", "color": unreal_color}),
                html.Td(f"{'+' if h['real'] >= 0 else ''}€{h['real']:,}" if h["real"] != 0 else "—", style={"textAlign": "right", "color": real_color}),
                html.Td("→", style={"textAlign": "right", "color": MUTED}),
            ], id={"type": "holding-row", "sym": h["sym"]}, n_clicks=0, style={"borderBottom": BORDER, "cursor": "pointer"})
        )

    return html.Table([
        html.Thead(html.Tr([
            html.Th(col, style={
                "color": MUTED,
                "fontSize": "10px",
                "letterSpacing": "0.1em",
                "textTransform": "uppercase",
                "padding": "0 12px 10px",
                "textAlign": "right" if i > 0 else "left",
                "borderBottom": BORDER,
            })
            for i, col in enumerate(["Asset", "Weight", "Price", "Unreal. P&L", "Real. P&L", ""])
        ])),
        html.Tbody(rows),
    ], style={"width": "100%", "borderCollapse": "collapse", "fontFamily": MONO, "fontSize": "13px"})


def render_overview():
    return html.Div([
        html.Div([
            html.Div(style={"width": "8px", "height": "8px", "borderRadius": "50%", "backgroundColor": ACCENT, "flexShrink": "0"}),
            html.Div([
                html.Strong("Portfolio Intelligence", style={"color": ACCENT}),
                html.Span(" — Biggest movers this month: "),
                html.Button("NVDA ▲18.4%", id={"type": "banner-chart-link", "sym": "NVDA"}, n_clicks=0,
                            style={"background": "none", "border": "none", "padding": 0, "color": ACCENT, "textDecoration": "underline", "cursor": "pointer", "fontWeight": "500", "fontFamily": MONO}),
                html.Span(" and "),
                html.Button("AAPL ▼6.2%", id={"type": "banner-chart-link", "sym": "AAPL"}, n_clicks=0,
                            style={"background": "none", "border": "none", "padding": 0, "color": RED, "textDecoration": "underline", "cursor": "pointer", "fontWeight": "500", "fontFamily": MONO}),
                html.Span(". Your portfolio is "),
                html.Span("87% correlated to US growth/tech", style={"color": YELLOW}),
                html.Span(". With "),
                html.Button("FOMC in 5 days", id={"type": "macro-link", "event": "FOMC"}, n_clicks=0,
                            style={"background": "none", "border": "none", "padding": 0, "color": YELLOW, "textDecoration": "underline", "cursor": "pointer", "fontWeight": "500", "fontFamily": MONO}),
                html.Span(", a +25bps surprise would compress duration names by "),
                html.Span("−3.8%", style={"color": RED}),
                html.Span(". "),
                html.Button("MSFT", id={"type": "banner-chart-link", "sym": "MSFT"}, n_clicks=0,
                            style={"background": "none", "border": "none", "padding": 0, "color": ACCENT, "textDecoration": "underline", "cursor": "pointer", "fontWeight": "500", "fontFamily": MONO}),
                html.Span(" and NVDA account for "),
                html.Span("62%", style={"color": RED}),
                html.Span(" of that exposure."),
            ], style={"fontSize": "12.5px", "lineHeight": "1.6"}),
        ], style={
            "display": "flex",
            "alignItems": "center",
            "gap": "16px",
            "padding": "16px 32px",
            "background": "linear-gradient(135deg, rgba(123,110,246,0.08), rgba(91,142,240,0.05))",
            "borderBottom": BORDER,
        }),

        html.Div([
            html.Div([
                html.Div([
                    html.Div([
                        html.Div(f"€{PORTFOLIO_VALUE:,.2f}", style={"fontFamily": "sans-serif", "fontSize": "36px", "fontWeight": "700", "letterSpacing": "-1px"}),
                        html.Div(f"▲ €{PORTFOLIO_PNL:,.2f} ({PORTFOLIO_PNL_PCT:.1f}%) all time", style={"fontSize": "13px", "color": GREEN, "marginTop": "6px"}),
                    ]),
                    html.Div([
                        metric_card("Sharpe", "1.42", GREEN),
                        metric_card("VaR 95%", "−€841", YELLOW),
                        metric_card("CVaR", "−€1,203", RED),
                        metric_card("Beta", "1.18"),
                    ], style={"display": "flex", "gap": "24px"}),
                ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start", "marginBottom": "28px"}),

                section_kicker("Efficient Frontier — Portfolio Position", "8px"),
                dcc.Graph(figure=build_frontier_chart(), config={"displayModeBar": False}, style={"border": BORDER, "borderRadius": "4px", "marginBottom": "28px"}),

                section_kicker("Holdings"),
                holdings_table(),
            ], style={"backgroundColor": "#0a0a0f", "padding": "28px 32px", "flex": "1", "minWidth": "0"}),

            html.Div([
                section_kicker("Allocation Breakdown", "8px"),
                dcc.Graph(figure=build_donut_chart(), config={"displayModeBar": False}),

                html.Div([
                    html.Div([
                        html.Div([
                            html.Span("■ ", style={"color": color, "fontSize": "12px"}),
                            html.Span(label, style={"color": MUTED, "fontSize": "11px"}),
                        ]),
                        html.Span(f"{pct}%", style={"fontSize": "12px", "fontWeight": "500"}),
                    ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "marginBottom": "8px"})
                    for label, pct, color in zip(ALLOCATION.keys(), ALLOCATION.values(), ALLOC_COLORS)
                ], style={"marginBottom": "24px"}),

                html.Hr(style={"borderColor": "#1e1e2e", "margin": "4px 0 20px"}),

                section_kicker("Risk Snapshot"),
                html.Div([
                    risk_card("VaR (1d, 95%)", "−1.8%", "€841 max daily loss", RED),
                    risk_card("CVaR / ES", "−2.5%", "Tail loss beyond VaR", RED),
                    risk_card("Sharpe", "1.42", "vs SPX: 0.91", GREEN),
                    risk_card("Max DD", "−14.2%", "Last 12 months", YELLOW),
                ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "10px", "marginBottom": "24px"}),

                html.Hr(style={"borderColor": "#1e1e2e", "margin": "4px 0 20px"}),

                section_kicker("Macro Calendar"),
                html.Div([
                    html.Div([
                        html.Span("⚡ FOMC Rate Decision", style={"color": YELLOW, "fontSize": "11px", "fontWeight": "500"}),
                        html.Span("in 5 days", style={"color": YELLOW, "fontSize": "10px", "opacity": "0.7"}),
                    ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "8px"}),
                    html.Div("Market pricing +25bps. Your bond (TLT) and growth equity exposure creates a dual headwind. Estimated portfolio impact:", style={"fontSize": "11px", "lineHeight": "1.6", "opacity": "0.85", "marginBottom": "10px"}),
                    html.Div([
                        html.Span("−3.8% shock", style={"background": "rgba(240,91,91,0.12)", "color": RED, "border": "1px solid rgba(240,91,91,0.2)", "padding": "3px 8px", "borderRadius": "3px", "fontSize": "10px", "marginRight": "8px"}),
                        html.Span("+1.2% hold", style={"background": "rgba(61,214,140,0.10)", "color": GREEN, "border": "1px solid rgba(61,214,140,0.2)", "padding": "3px 8px", "borderRadius": "3px", "fontSize": "10px", "marginRight": "8px"}),
                        html.Button("Open scenario", id={"type": "macro-link", "event": "FOMC"}, n_clicks=0,
                                    style={"background": "none", "border": "none", "padding": 0, "color": ACCENT, "textDecoration": "underline", "cursor": "pointer", "fontFamily": MONO, "fontSize": "10px"}),
                    ]),
                ], style={"background": "rgba(240,185,89,0.05)", "border": "1px solid rgba(240,185,89,0.2)", "borderRadius": "6px", "padding": "14px"}),
            ], style={"backgroundColor": "#111118", "borderLeft": BORDER, "padding": "28px 24px", "width": "340px", "flexShrink": "0"}),
        ], style={"display": "flex", "minHeight": "calc(100vh - 120px)"}),
    ])


def render_stock(sym):
    d = STOCK_DETAIL[sym]
    h = get_holding(sym)
    move_color = GREEN if d["day_move"].startswith("+") else RED

    tabs_style = {"backgroundColor": "#0a0a0f", "color": MUTED, "border": "none", "fontFamily": MONO, "fontSize": "11px"}
    selected_tabs_style = {"backgroundColor": "#0a0a0f", "color": ACCENT, "borderBottom": f"2px solid {ACCENT}", "fontFamily": MONO, "fontSize": "11px"}

    return html.Div([
        html.Button("← Back to Overview", id={"type": "back-btn", "target": "overview"}, n_clicks=0,
                    style={"background": "none", "border": "none", "color": MUTED, "fontSize": "12px", "cursor": "pointer", "fontFamily": MONO, "letterSpacing": "0.05em", "marginBottom": "24px"}),

        html.Div([
            html.Div([
                html.Div(sym[:2], style={
                    "width": "44px", "height": "44px", "borderRadius": "10px",
                    "background": f"linear-gradient(135deg, {h['color']}, {h['color']}88)",
                    "display": "flex", "alignItems": "center", "justifyContent": "center",
                    "fontFamily": "sans-serif", "fontWeight": "800", "fontSize": "16px",
                }),
                html.Div([
                    html.Div(sym, style={"fontFamily": "sans-serif", "fontSize": "24px", "fontWeight": "700", "letterSpacing": "-0.5px"}),
                    html.Div(h["name"], style={"color": MUTED, "fontSize": "12px", "marginTop": "2px"}),
                ]),
            ], style={"display": "flex", "alignItems": "center", "gap": "14px"}),
            html.Div([
                html.Div(format_price(h["price"]), style={"fontFamily": "sans-serif", "fontSize": "28px", "fontWeight": "700", "letterSpacing": "-0.5px"}),
                html.Div(d["day_move"], style={"fontSize": "13px", "color": move_color, "marginTop": "4px", "textAlign": "right"}),
            ]),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start", "marginBottom": "28px", "paddingBottom": "24px", "borderBottom": BORDER}),

        dcc.Tabs(id="stock-tabs", value="analyst", children=[
            dcc.Tab(label="Analyst View", value="analyst", style=tabs_style, selected_style=selected_tabs_style),
            dcc.Tab(label="Risk", value="risk", style=tabs_style, selected_style=selected_tabs_style),
            dcc.Tab(label="Exposure", value="exposure", style=tabs_style, selected_style=selected_tabs_style),
            dcc.Tab(label="Valuation", value="valuation", style=tabs_style, selected_style=selected_tabs_style),
        ], style={"marginBottom": "20px"}),

        html.Div(id="tab-content-stock", **{"data-sym": sym}),
    ], style={"padding": "32px", "maxWidth": "1100px", "margin": "0 auto"})


def render_chart(sym, highlight_idx=None, range_key="1M"):
    data = CHART_DATA[sym]
    dates, prices, events = get_chart_payload(sym, range_key)
    last_price = prices[-1]
    change_pct = (prices[-1] / prices[0]) * 100 - 100
    chg_label = format_change(change_pct, range_key)
    chg_color = GREEN if change_pct >= 0 else RED

    tag_styles = {
        "earnings": {"background": "rgba(123,110,246,0.15)", "color": "#7b6ef6"},
        "news": {"background": "rgba(91,142,240,0.12)", "color": "#5b8ef0"},
        "macro": {"background": "rgba(240,185,89,0.12)", "color": "#f0b959"},
        "undetermined": {"background": "rgba(107,107,138,0.15)", "color": "#6b6b8a"},
    }

    event_cards = []
    for i, ev in enumerate(events):
        is_active = highlight_idx == i
        is_up = ev["dir"] == "up"
        move_color = GREEN if is_up else RED
        prefix = "▲" if is_up else "▼"
        ts = tag_styles.get(ev["tag"], tag_styles["undetermined"])
        reason_text = ev["reason"] or "No clear catalyst identified. Move may reflect broader sector rotation or low-volume drift."

        event_cards.append(html.Div([
            html.Div(ev["date"], style={"color": MUTED, "fontSize": "10px", "letterSpacing": "0.08em", "textTransform": "uppercase", "marginBottom": "6px"}),
            html.Div(f"{prefix} {ev['move']}", style={"fontSize": "14px", "fontWeight": "500", "color": move_color, "marginBottom": "5px"}),
            html.Div(reason_text, style={"fontSize": "11px", "lineHeight": "1.6", "opacity": "0.8", "fontStyle": "italic" if not ev["reason"] else "normal"}),
            html.Span(ev["tag"].capitalize(), style={**ts, "display": "inline-block", "marginTop": "8px", "padding": "2px 8px", "borderRadius": "3px", "fontSize": "9px", "letterSpacing": "0.08em", "textTransform": "uppercase"}),
        ], id={"type": "event-card", "idx": i}, n_clicks=0,
           style={
               "backgroundColor": "#0a0a0f" if not is_active else "rgba(123,110,246,0.05)",
               "border": f"1px solid {ACCENT}" if is_active else BORDER,
               "borderRadius": "6px",
               "padding": "14px",
               "cursor": "pointer",
               "marginBottom": "10px",
           }))

    return html.Div([
        html.Div([
            html.Button("← Back", id={"type": "back-btn", "target": "overview"}, n_clicks=0,
                        style={"background": "none", "border": "none", "color": MUTED, "fontSize": "12px", "cursor": "pointer", "fontFamily": MONO}),
            html.Div([
                html.Span(sym, style={"fontFamily": "sans-serif", "fontSize": "18px", "fontWeight": "700", "marginRight": "12px"}),
                html.Span(format_price(last_price), style={"color": MUTED, "fontSize": "13px", "marginRight": "8px"}),
                html.Span(chg_label, style={"fontSize": "13px", "fontWeight": "500", "color": chg_color}),
            ]),
            html.Div(style={"width": "80px"}),
        ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "padding": "18px 32px", "borderBottom": BORDER}),

        html.Div([
            html.Div([
                html.Div([
                    html.Button(r, id={"type": "range-btn", "r": r}, n_clicks=0,
                                style={
                                    "padding": "4px 10px",
                                    "borderRadius": "3px",
                                    "border": BORDER,
                                    "background": ACCENT if r == range_key else "none",
                                    "color": "#fff" if r == range_key else MUTED,
                                    "fontFamily": MONO,
                                    "fontSize": "10px",
                                    "cursor": "pointer",
                                    "marginRight": "6px",
                                })
                    for r in ["1M", "3M", "6M", "1Y"]
                ], style={"marginBottom": "12px"}),
                dcc.Graph(id="price-chart", figure=build_price_chart(sym, highlight_idx, range_key), config={"displayModeBar": False}),
            ], style={"flex": "1", "padding": "24px 28px", "backgroundColor": "#0a0a0f", "minWidth": "0"}),

            html.Div([
                section_kicker("Price Events", "14px"),
                html.Div(event_cards),
            ], style={"width": "300px", "flexShrink": "0", "backgroundColor": "#111118", "borderLeft": BORDER, "padding": "24px 18px", "overflowY": "auto"}),
        ], style={"display": "flex", "flex": "1", "overflow": "hidden"}),
    ], style={"display": "flex", "flexDirection": "column", "height": "calc(100vh - 57px)"})


def render_watchlist():
    cards = []
    for h in HOLDINGS:
        d = STOCK_DETAIL[h["sym"]]
        cards.append(html.Div([
            html.Div([
                html.Div([
                    html.Span("● ", style={"color": h["color"], "fontSize": "12px"}),
                    html.Span(h["sym"], style={"fontFamily": "sans-serif", "fontSize": "20px", "fontWeight": "700"}),
                ]),
                html.Div(h["name"], style={"color": MUTED, "fontSize": "12px", "marginTop": "4px"}),
            ]),
            html.Div(WATCHLIST_NOTES[h["sym"]], style={"fontSize": "12px", "lineHeight": "1.7", "opacity": "0.9", "margin": "14px 0 16px"}),
            html.Div([
                html.Div([html.Span("Current", style={"color": MUTED, "fontSize": "10px"}), html.Div(format_price(h["price"]), style={"fontWeight": "600", "marginTop": "4px"})]),
                html.Div([html.Span("Consensus", style={"color": MUTED, "fontSize": "10px"}), html.Div(d["consensus"], style={"fontWeight": "600", "marginTop": "4px", "color": consensus_color(d['consensus'])})]),
                html.Div([html.Span("Target", style={"color": MUTED, "fontSize": "10px"}), html.Div(format_price(d["avg_target"]), style={"fontWeight": "600", "marginTop": "4px"})]),
            ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "12px", "marginBottom": "18px"}),
            html.Div([
                html.Button("Open detail", id={"type": "watchlist-stock-btn", "sym": h["sym"]}, n_clicks=0,
                            style={"background": "none", "border": BORDER, "color": "#e8e8f0", "padding": "8px 12px", "borderRadius": "6px", "cursor": "pointer", "fontFamily": MONO, "marginRight": "10px"}),
                html.Button("Open chart", id={"type": "watchlist-chart-btn", "sym": h["sym"]}, n_clicks=0,
                            style={"background": ACCENT, "border": f"1px solid {ACCENT}", "color": "#fff", "padding": "8px 12px", "borderRadius": "6px", "cursor": "pointer", "fontFamily": MONO}),
            ]),
        ], style={"backgroundColor": "#111118", "border": BORDER, "borderRadius": "10px", "padding": "20px"}))

    return html.Div([
        html.Div([
            html.Div("Watchlist", style={"fontFamily": "sans-serif", "fontSize": "30px", "fontWeight": "700", "letterSpacing": "-0.8px"}),
            html.Div("Track holdings, open detailed views, or jump straight into annotated price charts.", style={"fontSize": "13px", "color": MUTED, "marginTop": "6px"}),
        ], style={"marginBottom": "24px"}),
        html.Div(cards, style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"}),
    ], style={"padding": "32px", "maxWidth": "1150px", "margin": "0 auto"})


def scenario_card(title, body, impact, tone, button=False):
    tone_color = {"warn": YELLOW, "bad": RED, "good": GREEN}.get(tone, ACCENT)
    children = [
        html.Div(title, style={"fontFamily": "sans-serif", "fontSize": "20px", "fontWeight": "700", "marginBottom": "10px"}),
        html.Div(body, style={"fontSize": "12px", "lineHeight": "1.7", "opacity": "0.9", "marginBottom": "14px"}),
        html.Span(impact, style={"display": "inline-block", "padding": "4px 10px", "borderRadius": "999px", "fontSize": "10px", "border": f"1px solid {tone_color}55", "color": tone_color, "background": tone_color + "18"}),
    ]
    if button:
        children.append(
            html.Div([
                html.Button("Open full scenario", id={"type": "macro-link", "event": "FOMC"}, n_clicks=0,
                            style={"marginTop": "16px", "background": ACCENT, "border": f"1px solid {ACCENT}", "color": "#fff", "padding": "8px 12px", "borderRadius": "6px", "cursor": "pointer", "fontFamily": MONO})
            ])
        )
    return html.Div(children, style={"backgroundColor": "#111118", "border": BORDER, "borderRadius": "10px", "padding": "22px"})


def render_scenarios():
    return html.Div([
        html.Div([
            html.Div("Scenarios", style={"fontFamily": "sans-serif", "fontSize": "30px", "fontWeight": "700", "letterSpacing": "-0.8px"}),
            html.Div("Stress-test the portfolio against regime changes rather than only recent price moves.", style={"fontSize": "13px", "color": MUTED, "marginTop": "6px"}),
        ], style={"marginBottom": "24px"}),
        html.Div([
            scenario_card(
                "FOMC hawkish surprise",
                "The portfolio’s tech-duration concentration and TLT exposure create a non-linear response to rising real yields. This is the most important near-term macro event in the dashboard.",
                "Estimated portfolio shock: −3.8%",
                "bad",
                button=True,
            ),
            scenario_card(
                "Soft landing / lower inflation",
                "A gradual easing in inflation and stable growth would likely support both mega-cap quality and duration hedges. This is the best broad outcome for the current mix.",
                "Estimated portfolio lift: +2.4%",
                "good",
            ),
            scenario_card(
                "Commodity / geopolitical flare-up",
                "Gold likely helps, but long duration and high-beta growth may not hedge one another well if the shock is inflationary rather than deflationary.",
                "Estimated portfolio move: −0.9% to −1.8%",
                "warn",
            ),
        ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "16px"}),
    ], style={"padding": "32px", "maxWidth": "1200px", "margin": "0 auto"})


def render_fomc_page():
    return html.Div([
        html.Button("← Back to Scenarios", id={"type": "nav-btn", "page": "scenarios"}, n_clicks=0,
                    style={"background": "none", "border": "none", "color": MUTED, "fontSize": "12px", "cursor": "pointer", "fontFamily": MONO, "letterSpacing": "0.05em", "marginBottom": "24px"}),

        html.Div([
            html.Div([
                html.Div("FOMC Rate Decision", style={"fontFamily": "sans-serif", "fontSize": "32px", "fontWeight": "700", "letterSpacing": "-1px"}),
                html.Div("Macro scenario detail", style={"fontSize": "12px", "color": YELLOW, "marginTop": "8px"}),
            ]),
            html.Div([
                html.Span("Next event", style={"fontSize": "10px", "color": MUTED, "textTransform": "uppercase", "letterSpacing": "0.08em"}),
                html.Div("5 days", style={"fontFamily": "sans-serif", "fontSize": "28px", "fontWeight": "700", "marginTop": "4px"}),
            ], style={"textAlign": "right"}),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-start", "marginBottom": "24px"}),

        html.Div([
            html.Div([
                section_kicker("Scenario framing"),
                html.Div("Market pricing implies a modestly hawkish path, but your portfolio is positioned such that the sign of the surprise matters more than the size. Tech, duration and crypto all respond to discount-rate expectations, just with different convexity.", style={"fontSize": "13px", "lineHeight": "1.8", "opacity": "0.92"}),
                html.Div([
                    html.Div([html.Div("Hawkish", style={"fontSize": "10px", "color": MUTED, "textTransform": "uppercase"}), html.Div("−3.8%", style={"fontSize": "28px", "fontWeight": "700", "color": RED, "marginTop": "6px"}), html.Div("NVDA, MSFT and TLT take the largest hit.", style={"fontSize": "11px", "color": MUTED, "marginTop": "6px"})], style={"backgroundColor": "#0a0a0f", "border": BORDER, "borderRadius": "8px", "padding": "16px"}),
                    html.Div([html.Div("Base case", style={"fontSize": "10px", "color": MUTED, "textTransform": "uppercase"}), html.Div("+0.3%", style={"fontSize": "28px", "fontWeight": "700", "color": GREEN, "marginTop": "6px"}), html.Div("Little change; quality and gold cushion the outcome.", style={"fontSize": "11px", "color": MUTED, "marginTop": "6px"})], style={"backgroundColor": "#0a0a0f", "border": BORDER, "borderRadius": "8px", "padding": "16px"}),
                    html.Div([html.Div("Dovish", style={"fontSize": "10px", "color": MUTED, "textTransform": "uppercase"}), html.Div("+2.1%", style={"fontSize": "28px", "fontWeight": "700", "color": GREEN, "marginTop": "6px"}), html.Div("Duration and growth rerate together.", style={"fontSize": "11px", "color": MUTED, "marginTop": "6px"})], style={"backgroundColor": "#0a0a0f", "border": BORDER, "borderRadius": "8px", "padding": "16px"}),
                ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "12px", "marginTop": "18px"}),
            ], style={"backgroundColor": "#111118", "border": BORDER, "borderRadius": "10px", "padding": "24px"}),

            html.Div([
                section_kicker("Portfolio sensitivity"),
                html.Div([
                    html.Div([html.Span("NVDA / MSFT / AAPL", style={"fontSize": "12px"}), html.Span("Negative to higher real yields", style={"fontSize": "12px", "color": RED})], style={"display": "flex", "justifyContent": "space-between", "padding": "10px 0", "borderBottom": BORDER}),
                    html.Div([html.Span("TLT", style={"fontSize": "12px"}), html.Span("Strongly negative if policy path reprices up", style={"fontSize": "12px", "color": RED})], style={"display": "flex", "justifyContent": "space-between", "padding": "10px 0", "borderBottom": BORDER}),
                    html.Div([html.Span("GLD", style={"fontSize": "12px"}), html.Span("Mixed; better if real yields fall or risk rises", style={"fontSize": "12px", "color": YELLOW})], style={"display": "flex", "justifyContent": "space-between", "padding": "10px 0", "borderBottom": BORDER}),
                    html.Div([html.Span("BTC", style={"fontSize": "12px"}), html.Span("High-beta response to liquidity expectations", style={"fontSize": "12px", "color": YELLOW})], style={"display": "flex", "justifyContent": "space-between", "padding": "10px 0"}),
                ]),
                insight_box("The portfolio looks diversified by asset label, but FOMC sensitivity reveals a strong common driver: discount-rate exposure. That is why tech, long bonds and crypto can all struggle together under a hawkish surprise."),
            ], style={"backgroundColor": "#111118", "border": BORDER, "borderRadius": "10px", "padding": "24px"}),
        ], style={"display": "grid", "gridTemplateColumns": "1.5fr 1fr", "gap": "16px"}),
    ], style={"padding": "32px", "maxWidth": "1180px", "margin": "0 auto"})


def render_reports():
    report_cards = [
        ("Weekly exposure memo", "Summarises factor crowding, concentration and diversification gaps.", "Ready"),
        ("Scenario summary", "One-page view of hawkish, dovish and inflation-shock outcomes.", "Ready"),
        ("Valuation snapshot", "Rough DCF, RI and relative-value guide for the current holdings.", "Draft"),
    ]
    return html.Div([
        html.Div([
            html.Div("Reports", style={"fontFamily": "sans-serif", "fontSize": "30px", "fontWeight": "700", "letterSpacing": "-0.8px"}),
            html.Div("Mock reporting outputs for portfolio review and client-ready communication.", style={"fontSize": "13px", "color": MUTED, "marginTop": "6px"}),
        ], style={"marginBottom": "24px"}),
        html.Div([
            html.Div([
                html.Div(title, style={"fontFamily": "sans-serif", "fontSize": "20px", "fontWeight": "700", "marginBottom": "10px"}),
                html.Div(desc, style={"fontSize": "12px", "lineHeight": "1.7", "opacity": "0.9", "marginBottom": "14px"}),
                html.Span(status, style={"display": "inline-block", "padding": "4px 10px", "borderRadius": "999px", "fontSize": "10px", "border": BORDER, "color": ACCENT if status == "Ready" else YELLOW}),
            ], style={"backgroundColor": "#111118", "border": BORDER, "borderRadius": "10px", "padding": "22px"})
            for title, desc, status in report_cards
        ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "16px"}),
    ], style={"padding": "32px", "maxWidth": "1200px", "margin": "0 auto"})


def render_page(state):
    page = state.get("page", "overview")

    if page == "overview":
        return render_overview()
    if page == "watchlist":
        return render_watchlist()
    if page == "scenarios":
        return render_scenarios()
    if page == "reports":
        return render_reports()
    if page == "macro":
        return render_fomc_page()
    if page == "stock":
        sym = state.get("sym") or "NVDA"
        return render_stock(sym)
    if page == "chart":
        sym = state.get("chart_sym") or "NVDA"
        return render_chart(sym, state.get("highlight_idx"), state.get("chart_range", "1M"))
    return render_overview()


def render_shell(state):
    return html.Div([
        render_nav(state),
        html.Div(render_page(state), id="page-body"),
    ])


# ─────────────────────────────────────────────
# APP LAYOUT
# ─────────────────────────────────────────────

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY], suppress_callback_exceptions=True)
app.title = "Lens — Portfolio Intelligence"

app.layout = html.Div([
    dcc.Store(id="nav-store", data=DEFAULT_NAV),
    html.Div(id="app-shell"),
], style={**DARK, "minHeight": "100vh", "fontFamily": MONO})


# ─────────────────────────────────────────────
# CALLBACKS
# ─────────────────────────────────────────────

@app.callback(
    Output("app-shell", "children"),
    Input("nav-store", "data"),
)
def refresh_shell(state):
    state = state or DEFAULT_NAV
    return render_shell(state)


@app.callback(
    Output("nav-store", "data"),
    Input({"type": "nav-btn", "page": dash.ALL}, "n_clicks"),
    Input({"type": "holding-row", "sym": dash.ALL}, "n_clicks"),
    Input({"type": "banner-chart-link", "sym": dash.ALL}, "n_clicks"),
    Input({"type": "macro-link", "event": dash.ALL}, "n_clicks"),
    Input({"type": "watchlist-chart-btn", "sym": dash.ALL}, "n_clicks"),
    Input({"type": "watchlist-stock-btn", "sym": dash.ALL}, "n_clicks"),
    Input({"type": "back-btn", "target": dash.ALL}, "n_clicks"),
    Input({"type": "event-card", "idx": dash.ALL}, "n_clicks"),
    Input({"type": "range-btn", "r": dash.ALL}, "n_clicks"),
    State("nav-store", "data"),
    prevent_initial_call=True,
)
def update_nav_state(_nav_clicks, _holding_clicks, _banner_clicks, _macro_clicks,
                     _watchlist_chart_clicks, _watchlist_stock_clicks, _back_clicks,
                     _event_clicks, _range_clicks, state):
    state = dict(state or DEFAULT_NAV)
    triggered = ctx.triggered_id

    if not triggered:
        raise PreventUpdate

    if isinstance(triggered, dict):
        trigger_type = triggered.get("type")

        if trigger_type == "nav-btn":
            page = triggered["page"]
            if page == "overview":
                return {**DEFAULT_NAV, "page": "overview"}
            if page in {"watchlist", "scenarios", "reports"}:
                return {**state, "page": page, "highlight_idx": None}

        if trigger_type == "holding-row":
            return {**state, "page": "stock", "sym": triggered["sym"]}

        if trigger_type == "watchlist-stock-btn":
            return {**state, "page": "stock", "sym": triggered["sym"]}

        if trigger_type in {"banner-chart-link", "watchlist-chart-btn"}:
            return {**state, "page": "chart", "chart_sym": triggered["sym"], "chart_range": "1M", "highlight_idx": None}

        if trigger_type == "macro-link":
            return {**state, "page": "macro", "macro": triggered.get("event", "FOMC"), "highlight_idx": None}

        if trigger_type == "back-btn":
            return {**DEFAULT_NAV, "page": triggered.get("target", "overview")}

        if trigger_type == "event-card":
            return {**state, "highlight_idx": triggered["idx"]}

        if trigger_type == "range-btn":
            return {**state, "chart_range": triggered["r"]}

    raise PreventUpdate


@app.callback(
    Output("tab-content-stock", "children"),
    Input("stock-tabs", "value"),
    State("tab-content-stock", "data-sym"),
    prevent_initial_call=False,
)
def render_stock_tab(tab, sym):
    sym = sym or "NVDA"
    d = STOCK_DETAIL[sym]
    upside = round((d["avg_target"] / d["current"] - 1) * 100, 1)

    def row(label, val, sub=None, val_color=None):
        return html.Div([
            html.Span(label, style={"color": MUTED, "fontSize": "12px"}),
            html.Div([
                html.Div(val, style={"fontSize": "13px", "fontWeight": "500", "textAlign": "right", "color": val_color or "#e8e8f0"}),
                html.Div(sub, style={"fontSize": "10px", "color": MUTED, "textAlign": "right"}) if sub else None,
            ]),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "padding": "10px 0", "borderBottom": BORDER})

    card_style = {"backgroundColor": "#111118", "border": BORDER, "borderRadius": "8px", "padding": "20px"}

    if tab == "analyst":
        fill_pct = min(100, int((d["current"] / d["avg_target"]) * 100))
        return html.Div([
            html.Div([
                html.Div([
                    html.Div("Consensus Rating", style={"color": MUTED, "fontSize": "10px", "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "12px"}),
                    html.Div([
                        html.Span(d["consensus"], style={"background": consensus_color(d['consensus']) + "22", "color": consensus_color(d['consensus']), "border": f"1px solid {consensus_color(d['consensus'])}55", "padding": "6px 14px", "borderRadius": "4px", "fontWeight": "700", "fontSize": "14px", "marginRight": "12px"}),
                        html.Span(f"{d['buy']} Buy", style={"color": GREEN, "fontSize": "11px", "marginRight": "8px"}),
                        html.Span(f"{d['hold']} Hold", style={"color": YELLOW, "fontSize": "11px", "marginRight": "8px"}),
                        html.Span(f"{d['sell']} Sell", style={"color": RED, "fontSize": "11px"}),
                    ], style={"marginBottom": "14px"}),
                    row("Avg. Price Target", format_price(d["avg_target"]), val_color=GREEN),
                    row("Current Price", format_price(d["current"])),
                    row("Implied Upside", f"{upside:+.1f}%", val_color=GREEN if upside >= 0 else RED),
                    html.Div([
                        html.Div([
                            html.Span("Current", style={"fontSize": "10px", "color": MUTED}),
                            html.Span("Target", style={"fontSize": "10px", "color": MUTED}),
                        ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "6px", "marginTop": "12px"}),
                        html.Div(
                            html.Div(style={"width": f"{fill_pct}%", "height": "100%", "background": f"linear-gradient(90deg, {ACCENT}, {GREEN})", "borderRadius": "2px"}),
                            style={"height": "4px", "backgroundColor": "#1e1e2e", "borderRadius": "2px", "overflow": "hidden"},
                        ),
                    ]),
                ], style=card_style),
                html.Div([
                    html.Div("Recent Coverage", style={"color": MUTED, "fontSize": "10px", "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "12px"}),
                    *[
                        row(
                            bank,
                            f"{target} · {rating}",
                            val_color=GREEN if any(x in rating.lower() for x in ["buy", "ow", "overweight", "add", "accumulate"])
                            else (YELLOW if any(x in rating.lower() for x in ["neutral", "hold", "market perform"]) else RED)
                        )
                        for bank, target, rating in d["coverage"]
                    ],
                ], style=card_style),
            ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"}),
            insight_box(d["insight_analyst"]),
        ])

    if tab == "risk":
        metrics = [
            ("Value at Risk (1d, 95%)", d["var_1d"], "On a bad day, the position can still move materially.", RED, 65),
            ("Expected Shortfall (CVaR)", d["cvar"], "Average loss on the worst tail days.", RED, 78),
            ("Beta to S&P 500", d["beta"], "Measures market sensitivity, not total risk.", YELLOW, 74),
            ("Sharpe Ratio", d["sharpe"], "Risk-adjusted return relative to realised volatility.", GREEN, 72),
            ("Max Drawdown (12m)", d["max_dd"], "Deepest recent peak-to-trough loss.", YELLOW, 55),
            ("Volatility (30d Ann.)", d["vol"], "Useful for sizing, but incomplete on its own.", YELLOW, 82),
        ]
        bar_colors = {RED: RED, YELLOW: YELLOW, GREEN: GREEN}
        return html.Div([
            html.Div([
                html.Div([
                    html.Div(label, style={"color": MUTED, "fontSize": "10px", "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "8px"}),
                    html.Div(val, style={"fontFamily": "sans-serif", "fontSize": "26px", "fontWeight": "700", "letterSpacing": "-0.5px", "color": color, "marginBottom": "4px"}),
                    html.Div(sub, style={"color": MUTED, "fontSize": "11px", "lineHeight": "1.5", "marginBottom": "10px"}),
                    html.Div(
                        html.Div(style={"width": f"{pct}%", "height": "100%", "backgroundColor": bar_colors.get(color, color), "borderRadius": "2px"}),
                        style={"height": "3px", "backgroundColor": "#1e1e2e", "borderRadius": "2px", "overflow": "hidden"},
                    ),
                ], style=card_style)
                for label, val, sub, color, pct in metrics
            ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "14px"}),
            insight_box(d["insight_risk"]),
        ])

    if tab == "exposure":
        return html.Div([
            html.Div([
                html.Div([
                    html.Div("Factor Loadings", style={"color": MUTED, "fontSize": "10px", "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "12px"}),
                    *[
                        html.Div([
                            html.Span(name, style={"fontSize": "12px", "width": "130px", "flexShrink": "0"}),
                            html.Div(
                                html.Div(style={
                                    "width": f"{abs(val) * 100}%",
                                    "height": "100%",
                                    "backgroundColor": ACCENT if val > 0 else RED,
                                    "borderRadius": "2px",
                                    "marginLeft": "auto" if val < 0 else "0",
                                }),
                                style={"flex": "1", "height": "3px", "backgroundColor": "#1e1e2e", "borderRadius": "2px", "overflow": "hidden", "margin": "0 14px"},
                            ),
                            html.Span(f"{val:+.2f}", style={"fontSize": "12px", "fontWeight": "500", "color": GREEN if val > 0 else (RED if val < 0 else MUTED), "width": "50px", "textAlign": "right"}),
                        ], style={"display": "flex", "alignItems": "center", "padding": "10px 0", "borderBottom": BORDER})
                        for name, val in d["factors"]
                    ],
                ], style=card_style),
                html.Div([
                    html.Div("Sector & Geography", style={"color": MUTED, "fontSize": "10px", "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "12px"}),
                    row("Primary Sector", d["sector"]),
                    row("Geography", d["geography"]),
                    row("Revenue Exposure", d["revenue_exposure"], val_color=YELLOW),
                    row("Currency Risk", d["currency_risk"]),
                    row("Correlation to SPX", d["corr_spx"], val_color=YELLOW),
                ], style=card_style),
            ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"}),
            insight_box(d["insight_exposure"]),
        ])

    if tab == "valuation":
        return html.Div([
            html.Div([
                html.Div([
                    html.Div("Multiples vs Sector", style={"color": MUTED, "fontSize": "10px", "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "12px"}),
                    row("P/E (TTM)", d["pe"], val_color=YELLOW if d["pe"] != "—" else MUTED),
                    row("Forward P/E", d["fwd_pe"], val_color=YELLOW if d["fwd_pe"] != "—" else MUTED),
                    row("EV/EBITDA", d["ev_ebitda"], val_color=YELLOW if d["ev_ebitda"] != "—" else MUTED),
                    row("PEG Ratio", d["peg"], val_color=GREEN if d["peg"] not in {"—", "N/A"} else MUTED),
                ], style=card_style),
                html.Div([
                    html.Div("DCF Snapshot", style={"color": MUTED, "fontSize": "10px", "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "12px"}),
                    row("Intrinsic Value Est.", d["dcf"], "Bull / base / bear range"),
                    row("Current Price", format_price(d["current"]), "Relative to internal fair-value band"),
                    row("Revenue Growth", d["rev_growth"], val_color=GREEN if str(d["rev_growth"]).startswith("+") else MUTED),
                    row("EPS / Carry Driver", d["eps_growth"], val_color=GREEN if str(d["eps_growth"]).startswith("+") else MUTED),
                ], style=card_style),
            ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"}),
            insight_box(d["insight_valuation"]),
        ])

    return html.Div()


# ─────────────────────────────────────────────
# APP LAYOUT
# ─────────────────────────────────────────────

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY], suppress_callback_exceptions=True)
app.title = "Lens — Portfolio Intelligence"

app.layout = html.Div([
    dcc.Store(id="nav-store", data=DEFAULT_NAV),
    html.Div(id="app-shell"),
], style={**DARK, "minHeight": "100vh", "fontFamily": MONO})


# ─────────────────────────────────────────────
# CALLBACKS
# ─────────────────────────────────────────────

@app.callback(
    Output("app-shell", "children"),
    Input("nav-store", "data"),
)
def refresh_shell(state):
    state = state or DEFAULT_NAV
    return render_shell(state)


@app.callback(
    Output("nav-store", "data"),
    Input({"type": "nav-btn", "page": dash.ALL}, "n_clicks"),
    Input({"type": "holding-row", "sym": dash.ALL}, "n_clicks"),
    Input({"type": "banner-chart-link", "sym": dash.ALL}, "n_clicks"),
    Input({"type": "macro-link", "event": dash.ALL}, "n_clicks"),
    Input({"type": "watchlist-chart-btn", "sym": dash.ALL}, "n_clicks"),
    Input({"type": "watchlist-stock-btn", "sym": dash.ALL}, "n_clicks"),
    Input({"type": "back-btn", "target": dash.ALL}, "n_clicks"),
    Input({"type": "event-card", "idx": dash.ALL}, "n_clicks"),
    Input({"type": "range-btn", "r": dash.ALL}, "n_clicks"),
    State("nav-store", "data"),
    prevent_initial_call=True,
)
def update_nav_state(_nav_clicks, _holding_clicks, _banner_clicks, _macro_clicks,
                     _watchlist_chart_clicks, _watchlist_stock_clicks, _back_clicks,
                     _event_clicks, _range_clicks, state):
    state = dict(state or DEFAULT_NAV)
    triggered = ctx.triggered_id

    if not triggered:
        raise PreventUpdate

    if isinstance(triggered, dict):
        trigger_type = triggered.get("type")

        if trigger_type == "nav-btn":
            page = triggered["page"]
            if page == "overview":
                return {**DEFAULT_NAV, "page": "overview"}
            if page in {"watchlist", "scenarios", "reports"}:
                return {**state, "page": page, "highlight_idx": None}

        if trigger_type == "holding-row":
            return {**state, "page": "stock", "sym": triggered["sym"]}

        if trigger_type == "watchlist-stock-btn":
            return {**state, "page": "stock", "sym": triggered["sym"]}

        if trigger_type in {"banner-chart-link", "watchlist-chart-btn"}:
            return {**state, "page": "chart", "chart_sym": triggered["sym"], "chart_range": "1M", "highlight_idx": None}

        if trigger_type == "macro-link":
            return {**state, "page": "macro", "macro": triggered.get("event", "FOMC"), "highlight_idx": None}

        if trigger_type == "back-btn":
            return {**DEFAULT_NAV, "page": triggered.get("target", "overview")}

        if trigger_type == "event-card":
            return {**state, "highlight_idx": triggered["idx"]}

        if trigger_type == "range-btn":
            return {**state, "chart_range": triggered["r"]}

    raise PreventUpdate


@app.callback(
    Output("tab-content-stock", "children"),
    Input("stock-tabs", "value"),
    State("tab-content-stock", "data-sym"),
    prevent_initial_call=False,
)
def render_stock_tab(tab, sym):
    sym = sym or "NVDA"
    d = STOCK_DETAIL[sym]
    upside = round((d["avg_target"] / d["current"] - 1) * 100, 1)

    def row(label, val, sub=None, val_color=None):
        return html.Div([
            html.Span(label, style={"color": MUTED, "fontSize": "12px"}),
            html.Div([
                html.Div(val, style={"fontSize": "13px", "fontWeight": "500", "textAlign": "right", "color": val_color or "#e8e8f0"}),
                html.Div(sub, style={"fontSize": "10px", "color": MUTED, "textAlign": "right"}) if sub else None,
            ]),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center", "padding": "10px 0", "borderBottom": BORDER})

    card_style = {"backgroundColor": "#111118", "border": BORDER, "borderRadius": "8px", "padding": "20px"}

    if tab == "analyst":
        fill_pct = min(100, int((d["current"] / d["avg_target"]) * 100))
        return html.Div([
            html.Div([
                html.Div([
                    html.Div("Consensus Rating", style={"color": MUTED, "fontSize": "10px", "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "12px"}),
                    html.Div([
                        html.Span(d["consensus"], style={"background": consensus_color(d['consensus']) + "22", "color": consensus_color(d['consensus']), "border": f"1px solid {consensus_color(d['consensus'])}55", "padding": "6px 14px", "borderRadius": "4px", "fontWeight": "700", "fontSize": "14px", "marginRight": "12px"}),
                        html.Span(f"{d['buy']} Buy", style={"color": GREEN, "fontSize": "11px", "marginRight": "8px"}),
                        html.Span(f"{d['hold']} Hold", style={"color": YELLOW, "fontSize": "11px", "marginRight": "8px"}),
                        html.Span(f"{d['sell']} Sell", style={"color": RED, "fontSize": "11px"}),
                    ], style={"marginBottom": "14px"}),
                    row("Avg. Price Target", format_price(d["avg_target"]), val_color=GREEN),
                    row("Current Price", format_price(d["current"])),
                    row("Implied Upside", f"{upside:+.1f}%", val_color=GREEN if upside >= 0 else RED),
                    html.Div([
                        html.Div([
                            html.Span("Current", style={"fontSize": "10px", "color": MUTED}),
                            html.Span("Target", style={"fontSize": "10px", "color": MUTED}),
                        ], style={"display": "flex", "justifyContent": "space-between", "marginBottom": "6px", "marginTop": "12px"}),
                        html.Div(
                            html.Div(style={"width": f"{fill_pct}%", "height": "100%", "background": f"linear-gradient(90deg, {ACCENT}, {GREEN})", "borderRadius": "2px"}),
                            style={"height": "4px", "backgroundColor": "#1e1e2e", "borderRadius": "2px", "overflow": "hidden"},
                        ),
                    ]),
                ], style=card_style),
                html.Div([
                    html.Div("Recent Coverage", style={"color": MUTED, "fontSize": "10px", "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "12px"}),
                    *[
                        row(
                            bank,
                            f"{target} · {rating}",
                            val_color=GREEN if any(x in rating.lower() for x in ["buy", "ow", "overweight", "add", "accumulate"])
                            else (YELLOW if any(x in rating.lower() for x in ["neutral", "hold", "market perform"]) else RED)
                        )
                        for bank, target, rating in d["coverage"]
                    ],
                ], style=card_style),
            ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"}),
            insight_box(d["insight_analyst"]),
        ])

    if tab == "risk":
        metrics = [
            ("Value at Risk (1d, 95%)", d["var_1d"], "On a bad day, the position can still move materially.", RED, 65),
            ("Expected Shortfall (CVaR)", d["cvar"], "Average loss on the worst tail days.", RED, 78),
            ("Beta to S&P 500", d["beta"], "Measures market sensitivity, not total risk.", YELLOW, 74),
            ("Sharpe Ratio", d["sharpe"], "Risk-adjusted return relative to realised volatility.", GREEN, 72),
            ("Max Drawdown (12m)", d["max_dd"], "Deepest recent peak-to-trough loss.", YELLOW, 55),
            ("Volatility (30d Ann.)", d["vol"], "Useful for sizing, but incomplete on its own.", YELLOW, 82),
        ]
        bar_colors = {RED: RED, YELLOW: YELLOW, GREEN: GREEN}
        return html.Div([
            html.Div([
                html.Div([
                    html.Div(label, style={"color": MUTED, "fontSize": "10px", "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "8px"}),
                    html.Div(val, style={"fontFamily": "sans-serif", "fontSize": "26px", "fontWeight": "700", "letterSpacing": "-0.5px", "color": color, "marginBottom": "4px"}),
                    html.Div(sub, style={"color": MUTED, "fontSize": "11px", "lineHeight": "1.5", "marginBottom": "10px"}),
                    html.Div(
                        html.Div(style={"width": f"{pct}%", "height": "100%", "backgroundColor": bar_colors.get(color, color), "borderRadius": "2px"}),
                        style={"height": "3px", "backgroundColor": "#1e1e2e", "borderRadius": "2px", "overflow": "hidden"},
                    ),
                ], style=card_style)
                for label, val, sub, color, pct in metrics
            ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr", "gap": "14px"}),
            insight_box(d["insight_risk"]),
        ])

    if tab == "exposure":
        return html.Div([
            html.Div([
                html.Div([
                    html.Div("Factor Loadings", style={"color": MUTED, "fontSize": "10px", "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "12px"}),
                    *[
                        html.Div([
                            html.Span(name, style={"fontSize": "12px", "width": "130px", "flexShrink": "0"}),
                            html.Div(
                                html.Div(style={
                                    "width": f"{abs(val) * 100}%",
                                    "height": "100%",
                                    "backgroundColor": ACCENT if val > 0 else RED,
                                    "borderRadius": "2px",
                                    "marginLeft": "auto" if val < 0 else "0",
                                }),
                                style={"flex": "1", "height": "3px", "backgroundColor": "#1e1e2e", "borderRadius": "2px", "overflow": "hidden", "margin": "0 14px"},
                            ),
                            html.Span(f"{val:+.2f}", style={"fontSize": "12px", "fontWeight": "500", "color": GREEN if val > 0 else (RED if val < 0 else MUTED), "width": "50px", "textAlign": "right"}),
                        ], style={"display": "flex", "alignItems": "center", "padding": "10px 0", "borderBottom": BORDER})
                        for name, val in d["factors"]
                    ],
                ], style=card_style),
                html.Div([
                    html.Div("Sector & Geography", style={"color": MUTED, "fontSize": "10px", "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "12px"}),
                    row("Primary Sector", d["sector"]),
                    row("Geography", d["geography"]),
                    row("Revenue Exposure", d["revenue_exposure"], val_color=YELLOW),
                    row("Currency Risk", d["currency_risk"]),
                    row("Correlation to SPX", d["corr_spx"], val_color=YELLOW),
                ], style=card_style),
            ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"}),
            insight_box(d["insight_exposure"]),
        ])

    if tab == "valuation":
        return html.Div([
            html.Div([
                html.Div([
                    html.Div("Multiples vs Sector", style={"color": MUTED, "fontSize": "10px", "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "12px"}),
                    row("P/E (TTM)", d["pe"], val_color=YELLOW if d["pe"] != "—" else MUTED),
                    row("Forward P/E", d["fwd_pe"], val_color=YELLOW if d["fwd_pe"] != "—" else MUTED),
                    row("EV/EBITDA", d["ev_ebitda"], val_color=YELLOW if d["ev_ebitda"] != "—" else MUTED),
                    row("PEG Ratio", d["peg"], val_color=GREEN if d["peg"] not in {"—", "N/A"} else MUTED),
                ], style=card_style),
                html.Div([
                    html.Div("DCF Snapshot", style={"color": MUTED, "fontSize": "10px", "letterSpacing": "0.1em", "textTransform": "uppercase", "marginBottom": "12px"}),
                    row("Intrinsic Value Est.", d["dcf"], "Bull / base / bear range"),
                    row("Current Price", format_price(d["current"]), "Relative to internal fair-value band"),
                    row("Revenue Growth", d["rev_growth"], val_color=GREEN if str(d["rev_growth"]).startswith("+") else MUTED),
                    row("EPS / Carry Driver", d["eps_growth"], val_color=GREEN if str(d["eps_growth"]).startswith("+") else MUTED),
                ], style=card_style),
            ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"}),
            insight_box(d["insight_valuation"]),
        ])

    return html.Div()


def render_page(state):
    page = state.get("page", "overview")

    if page == "overview":
        return render_overview()
    if page == "watchlist":
        return render_watchlist()
    if page == "scenarios":
        return render_scenarios()
    if page == "reports":
        return render_reports()
    if page == "macro":
        return render_fomc_page()
    if page == "stock":
        sym = state.get("sym") or "NVDA"
        return render_stock(sym)
    if page == "chart":
        sym = state.get("chart_sym") or "NVDA"
        return render_chart(sym, state.get("highlight_idx"), state.get("chart_range", "1M"))
    return render_overview()


def render_shell(state):
    return html.Div([
        render_nav(state),
        html.Div(render_page(state), id="page-body"),
    ])


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)