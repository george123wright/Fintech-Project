from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
from typing import Any

import pandas as pd
import yfinance as yf


@dataclass
class YahooSecuritySnapshot:
    symbol: str
    as_of_date: date
    current_price: float | None
    target_mean: float | None
    target_high: float | None
    target_low: float | None
    analyst_count: int | None
    recommendation_key: str | None
    recommendation_mean: float | None
    market_cap: float | None
    shares_outstanding: float | None
    free_cashflow: float | None
    trailing_eps: float | None
    forward_eps: float | None
    book_value_per_share: float | None
    roe: float | None
    pe: float | None
    forward_pe: float | None
    pb: float | None
    ev_ebitda: float | None
    sector: str | None
    industry: str | None
    growth_proxy: float | None


@dataclass
class YahooMarketEvent:
    id: str
    date: datetime
    event_type: str
    title: str
    summary: str
    detail: str | None
    link_target: str


@dataclass
class YahooCorporateActionRow:
    date: datetime
    action_type: str
    value: float
    description: str


@dataclass
class YahooInsiderTransactionRow:
    date: datetime | None
    insider: str | None
    position: str | None
    transaction: str | None
    shares: float | None
    value: float | None
    ownership: str | None
    text: str | None


@dataclass
class YahooAnalystRevisionRow:
    date: datetime
    firm: str | None
    action: str | None
    to_grade: str | None
    from_grade: str | None
    current_price_target: float | None
    prior_price_target: float | None
    price_target_action: str | None


@dataclass
class YahooNewsArticle:
    id: str
    title: str
    summary: str | None
    pub_date: datetime | None
    provider: str | None
    url: str | None
    thumbnail_url: str | None
    content_type: str | None
    symbols: list[str]


@dataclass
class YahooSecurityEventsPayload:
    symbol: str
    status: str
    warnings: list[str]
    events: list[YahooMarketEvent]
    corporate_actions: list[YahooCorporateActionRow]
    insider_transactions: list[YahooInsiderTransactionRow]
    analyst_revisions: list[YahooAnalystRevisionRow]


@dataclass
class YahooAnalystDetailPayload:
    symbol: str
    status: str
    warnings: list[str]
    snapshot: dict[str, Any]
    coverage: dict[str, Any]
    target_scenarios: list[dict[str, Any]]
    current_recommendations: list[dict[str, Any]]
    recommendations_history: list[dict[str, Any]]
    recommendations_table: list[dict[str, Any]]
    eps_trend: list[dict[str, Any]]
    eps_revisions: list[dict[str, Any]]
    earnings_estimate: list[dict[str, Any]]
    revenue_estimate: list[dict[str, Any]]
    growth_estimates: list[dict[str, Any]]


@dataclass
class YahooSecurityNewsPayload:
    symbol: str
    status: str
    warnings: list[str]
    articles: list[YahooNewsArticle]


@dataclass
class YahooPortfolioNewsPayload:
    status: str
    warnings: list[str]
    articles: list[YahooNewsArticle]


@dataclass
class YahooShareholderBreakdownRow:
    label: str
    value: float | None
    display_value: str | None


@dataclass
class YahooInstitutionalHolderRow:
    date_reported: date | None
    holder: str
    pct_held: float | None
    shares: float | None
    value: float | None
    pct_change: float | None


@dataclass
class YahooStockOverviewPayload:
    symbol: str
    status: str
    warnings: list[str]
    name: str | None
    description: str | None
    industry: str | None
    sector: str | None
    country: str | None
    full_address: str | None
    website: str | None
    market_cap: float | None
    current_price: float | None
    daily_return: float | None
    ytd_return: float | None
    one_year_return: float | None
    beta: float | None
    pe: float | None
    dividend_yield: float | None
    shareholder_breakdown: list[YahooShareholderBreakdownRow]
    institutional_holders: list[YahooInstitutionalHolderRow]


@dataclass
class YahooFinancialStatementsPayload:
    symbol: str
    status: str
    warnings: list[str]
    income_statement_annual: list[dict[str, Any]]
    income_statement_quarterly: list[dict[str, Any]]
    balance_sheet_annual: list[dict[str, Any]]
    balance_sheet_quarterly: list[dict[str, Any]]
    cashflow_annual: list[dict[str, Any]]
    cashflow_quarterly: list[dict[str, Any]]


@dataclass
class YahooFinancialRatioMetric:
    key: str
    label: str
    category: str
    unit: str
    value: float | None
    source: str
    description: str


@dataclass
class YahooFinancialRatiosPayload:
    symbol: str
    status: str
    warnings: list[str]
    annual: list[YahooFinancialRatioMetric]
    quarterly: list[YahooFinancialRatioMetric]


@dataclass
class YahooForwardEstimateSnapshot:
    symbol: str
    as_of_date: date
    status: str
    warnings: list[str]
    fy0_revenue_avg: float | None
    fy0_revenue_low: float | None
    fy0_revenue_high: float | None
    fy1_revenue_avg: float | None
    fy1_revenue_low: float | None
    fy1_revenue_high: float | None
    fy0_eps_avg: float | None
    fy0_eps_low: float | None
    fy0_eps_high: float | None
    fy1_eps_avg: float | None
    fy1_eps_low: float | None
    fy1_eps_high: float | None
    revenue_analyst_count_fy0: int | None
    revenue_analyst_count_fy1: int | None
    eps_analyst_count_fy0: int | None
    eps_analyst_count_fy1: int | None


@dataclass
class YahooMarketRateSnapshot:
    as_of_date: date
    status: str
    warnings: list[str]
    market_symbol: str
    risk_free_symbol: str
    market_return_5y: float | None
    risk_free_rate: float | None
    erp_5y: float | None
    observations: int


def _as_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _as_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    return raw or None


def _to_datetime(value: Any) -> datetime | None:
    try:
        ts = pd.to_datetime(value, errors="coerce")
    except Exception:
        return None
    if pd.isna(ts):
        return None
    if isinstance(ts, pd.Timestamp):
        if ts.tzinfo is not None:
            ts = ts.tz_convert(None)
        return ts.to_pydatetime()
    return None


def _to_date(value: Any) -> date | None:
    dt = _to_datetime(value)
    if dt is None:
        return None
    return dt.date()


def _extract_close_series(raw: pd.DataFrame, symbol: str) -> pd.Series:
    if raw.empty:
        return pd.Series(dtype=float, name=symbol)

    if isinstance(raw.columns, pd.MultiIndex):
        if ("Close", symbol) in raw.columns:
            close = raw[("Close", symbol)]
        elif "Close" in raw.columns.get_level_values(0):
            close = raw["Close"].iloc[:, 0]
        else:
            return pd.Series(dtype=float, name=symbol)
    else:
        close = raw.get("Close")
        if close is None:
            return pd.Series(dtype=float, name=symbol)

    close = pd.to_numeric(close, errors="coerce").dropna()
    close.name = symbol
    return close


def _get_first_column(df: pd.DataFrame) -> str:
    return str(df.columns[0]) if len(df.columns) > 0 else "Date"


def _to_json_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        ts = value.tz_convert(None) if value.tzinfo is not None else value
        return ts.isoformat()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, (int, float, str, bool)):
        return value
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:  # pragma: no cover - defensive fallback
            pass
    return str(value)


def _frame_to_rows(df: Any, *, max_rows: int = 200) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []

    work = df.copy()
    if isinstance(work.index, pd.MultiIndex) or not isinstance(work.index, pd.RangeIndex):
        work = work.reset_index()

    if len(work) > max_rows:
        work = work.head(max_rows)

    rows: list[dict[str, Any]] = []
    for _, row in work.iterrows():
        out: dict[str, Any] = {}
        for col in work.columns:
            out[str(col)] = _to_json_scalar(row.get(col))
        rows.append(out)
    return rows


def _statement_frame_to_rows(df: Any, *, max_rows: int = 200) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []

    work = df.copy()
    work.index = work.index.map(lambda item: str(item))
    work = work.reset_index().rename(columns={"index": "Metric"})

    column_map: dict[str, str] = {}
    for column in work.columns:
        col_name = str(column)
        if col_name == "Metric":
            column_map[col_name] = col_name
            continue

        try:
            ts = pd.to_datetime(column, errors="coerce")
        except Exception:
            ts = pd.NaT

        if pd.isna(ts):
            column_map[col_name] = col_name
        else:
            if isinstance(ts, pd.Timestamp) and ts.tzinfo is not None:
                ts = ts.tz_convert(None)
            column_map[col_name] = ts.date().isoformat()

    work.columns = [column_map.get(str(col), str(col)) for col in work.columns]
    value_cols = [col for col in work.columns if col != "Metric"]

    def _sort_key(col: str) -> tuple[int, float]:
        try:
            ts = datetime.fromisoformat(col)
            return (0, -ts.timestamp())
        except ValueError:
            return (1, 0.0)

    ordered_cols = sorted(value_cols, key=_sort_key)
    work = work[["Metric", *ordered_cols]]

    if len(work) > max_rows:
        work = work.head(max_rows)

    rows: list[dict[str, Any]] = []
    for _, row in work.iterrows():
        out: dict[str, Any] = {}
        for col in work.columns:
            out[str(col)] = _to_json_scalar(row.get(col))
        rows.append(out)
    return rows


def _normalize_metric_name(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _get_row_series(df: Any, aliases: list[str]) -> pd.Series | None:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None

    index_map: dict[str, Any] = {}
    for idx in df.index:
        norm = _normalize_metric_name(str(idx))
        if norm and norm not in index_map:
            index_map[norm] = idx

    for alias in aliases:
        key = _normalize_metric_name(alias)
        target_idx = index_map.get(key)
        if target_idx is None:
            continue
        row = df.loc[target_idx]
        if isinstance(row, pd.DataFrame):
            if row.empty:
                continue
            row = row.iloc[0]
        if isinstance(row, pd.Series):
            return row
    return None


def _latest_prev_from_row(row: pd.Series | None) -> tuple[float | None, float | None]:
    if row is None:
        return None, None
    values: list[float] = []
    for raw in row.values:
        val = _as_float(raw)
        if val is not None:
            values.append(val)
    if not values:
        return None, None
    latest = values[0]
    prev = values[1] if len(values) > 1 else None
    return latest, prev


def _metric_latest_prev(df: Any, aliases: list[str]) -> tuple[float | None, float | None]:
    return _latest_prev_from_row(_get_row_series(df, aliases))


def _first_info_value(info: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        val = _as_float(info.get(key))
        if val is not None:
            return val
    return None


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None:
        return None
    if abs(denominator) < 1e-12:
        return None
    return numerator / denominator


def _avg_two(latest: float | None, prev: float | None) -> float | None:
    if latest is None and prev is None:
        return None
    if latest is None:
        return prev
    if prev is None:
        return latest
    return (latest + prev) / 2.0


def _compute_ratio_metrics(
    *,
    income_df: pd.DataFrame,
    balance_df: pd.DataFrame,
    cashflow_df: pd.DataFrame,
    info: dict[str, Any],
    fast_info: dict[str, Any],
) -> list[YahooFinancialRatioMetric]:
    revenue, revenue_prev = _metric_latest_prev(income_df, ["Total Revenue", "Operating Revenue", "Revenue"])
    gross_profit, _ = _metric_latest_prev(income_df, ["Gross Profit"])
    operating_income, _ = _metric_latest_prev(income_df, ["Operating Income", "Total Operating Income As Reported"])
    ebitda, _ = _metric_latest_prev(income_df, ["EBITDA", "Normalized EBITDA"])
    ebit, _ = _metric_latest_prev(income_df, ["EBIT"])
    net_income, net_income_prev = _metric_latest_prev(
        income_df,
        [
            "Net Income",
            "Net Income Common Stockholders",
            "Net Income Including Noncontrolling Interests",
            "Net Income Continuous Operations",
        ],
    )
    pretax_income, _ = _metric_latest_prev(income_df, ["Pretax Income"])
    tax_provision, _ = _metric_latest_prev(income_df, ["Tax Provision"])
    tax_rate, _ = _metric_latest_prev(income_df, ["Tax Rate For Calcs"])
    diluted_eps, diluted_eps_prev = _metric_latest_prev(income_df, ["Diluted EPS"])
    cost_of_revenue, _ = _metric_latest_prev(income_df, ["Cost Of Revenue", "Reconciled Cost Of Revenue"])
    interest_expense, _ = _metric_latest_prev(income_df, ["Interest Expense", "Interest Expense Non Operating"])

    total_assets, total_assets_prev = _metric_latest_prev(balance_df, ["Total Assets"])
    total_equity, total_equity_prev = _metric_latest_prev(
        balance_df,
        ["Stockholders Equity", "Total Equity Gross Minority Interest", "Common Stock Equity", "Total Equity"],
    )
    current_assets, _ = _metric_latest_prev(balance_df, ["Current Assets", "Total Current Assets"])
    current_liabilities, _ = _metric_latest_prev(balance_df, ["Current Liabilities", "Total Current Liabilities"])
    receivables, receivables_prev = _metric_latest_prev(balance_df, ["Accounts Receivable", "Receivables"])
    inventory, inventory_prev = _metric_latest_prev(balance_df, ["Inventory", "Net Inventory"])
    cash_short, cash_short_prev = _metric_latest_prev(
        balance_df,
        [
            "Cash Cash Equivalents And Short Term Investments",
            "Cash And Cash Equivalents",
            "Cash And Short Term Investments",
        ],
    )
    short_term_investments, _ = _metric_latest_prev(balance_df, ["Other Short Term Investments", "Short Term Investments"])
    total_debt, total_debt_prev = _metric_latest_prev(balance_df, ["Total Debt"])
    net_debt, _ = _metric_latest_prev(balance_df, ["Net Debt"])
    invested_capital, invested_capital_prev = _metric_latest_prev(balance_df, ["Invested Capital"])

    operating_cash_flow, _ = _metric_latest_prev(
        cashflow_df,
        ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    )
    free_cash_flow, free_cash_flow_prev = _metric_latest_prev(cashflow_df, ["Free Cash Flow"])
    capex, _ = _metric_latest_prev(cashflow_df, ["Capital Expenditure", "Purchase Of PPE"])
    dividends_paid, _ = _metric_latest_prev(cashflow_df, ["Cash Dividends Paid", "Common Stock Dividend Paid"])
    buybacks, _ = _metric_latest_prev(cashflow_df, ["Repurchase Of Capital Stock", "Common Stock Payments"])

    current_price = _first_info_value(info, ["currentPrice", "regularMarketPrice"])
    if current_price is None:
        current_price = _as_float(fast_info.get("lastPrice"))
    market_cap = _first_info_value(info, ["marketCap"])
    enterprise_value = _first_info_value(info, ["enterpriseValue"])
    shares_outstanding = _first_info_value(info, ["sharesOutstanding", "impliedSharesOutstanding"])
    trailing_pe_info = _first_info_value(info, ["trailingPE"])
    forward_pe_info = _first_info_value(info, ["forwardPE"])
    price_to_sales_info = _first_info_value(info, ["priceToSalesTrailing12Months"])
    price_to_book_info = _first_info_value(info, ["priceToBook"])
    dividend_yield = _first_info_value(info, ["trailingAnnualDividendYield", "dividendYield"])
    if dividend_yield is not None and dividend_yield > 1:
        dividend_yield = dividend_yield / 100.0

    if tax_rate is None:
        tax_rate = _safe_div(tax_provision, pretax_income)
    if tax_rate is not None and tax_rate > 1:
        tax_rate = tax_rate / 100.0
    if tax_rate is not None:
        tax_rate = max(0.0, min(0.6, tax_rate))

    avg_assets = _avg_two(total_assets, total_assets_prev)
    avg_equity = _avg_two(total_equity, total_equity_prev)
    avg_receivables = _avg_two(receivables, receivables_prev)
    avg_inventory = _avg_two(inventory, inventory_prev)
    avg_invested_capital = _avg_two(invested_capital, invested_capital_prev)

    if avg_invested_capital is None:
        constructed_latest = None
        if total_debt is not None and total_equity is not None and cash_short is not None:
            constructed_latest = total_debt + total_equity - cash_short
        constructed_prev = None
        if total_debt_prev is not None and total_equity_prev is not None and cash_short_prev is not None:
            constructed_prev = total_debt_prev + total_equity_prev - cash_short_prev
        avg_invested_capital = _avg_two(constructed_latest, constructed_prev)

    if net_debt is None and total_debt is not None and cash_short is not None:
        net_debt = total_debt - cash_short

    if current_assets is None and receivables is not None and cash_short is not None and inventory is not None:
        current_assets = receivables + cash_short + inventory

    if cash_short is None and short_term_investments is not None:
        cash_short = short_term_investments
    elif cash_short is not None and short_term_investments is not None:
        cash_short = max(cash_short, short_term_investments)

    trailing_pe_calc = _safe_div(current_price, diluted_eps)
    trailing_pe = trailing_pe_info if trailing_pe_info is not None else trailing_pe_calc
    price_to_sales_calc = _safe_div(market_cap, revenue)
    price_to_sales = price_to_sales_info if price_to_sales_info is not None else price_to_sales_calc
    price_to_book_calc = _safe_div(market_cap, total_equity)
    price_to_book = price_to_book_info if price_to_book_info is not None else price_to_book_calc

    nopat = operating_income
    if operating_income is not None and tax_rate is not None:
        nopat = operating_income * (1.0 - tax_rate)

    quick_assets = None
    if cash_short is not None or receivables is not None:
        quick_assets = (cash_short or 0.0) + (receivables or 0.0)

    metrics: list[YahooFinancialRatioMetric] = []

    def add_metric(
        key: str,
        label: str,
        category: str,
        unit: str,
        value: float | None,
        source: str,
        description: str,
    ) -> None:
        metrics.append(
            YahooFinancialRatioMetric(
                key=key,
                label=label,
                category=category,
                unit=unit,
                value=value,
                source=source,
                description=description,
            )
        )

    add_metric("trailing_pe", "Trailing P/E", "Valuation", "x", trailing_pe, "info/statements", "Price divided by trailing earnings per share.")
    add_metric("forward_pe", "Forward P/E", "Valuation", "x", forward_pe_info, "info", "Price divided by forward EPS estimate.")
    add_metric("price_to_sales", "Price / Sales", "Valuation", "x", price_to_sales, "info/statements", "Market capitalization divided by total revenue.")
    add_metric("price_to_book", "Price / Book", "Valuation", "x", price_to_book, "info/statements", "Market capitalization divided by book equity.")
    add_metric("ev_to_sales", "EV / Sales", "Valuation", "x", _safe_div(enterprise_value, revenue), "info/statements", "Enterprise value divided by revenue.")
    add_metric("ev_to_ebitda", "EV / EBITDA", "Valuation", "x", _safe_div(enterprise_value, ebitda), "info/statements", "Enterprise value divided by EBITDA.")
    add_metric("market_cap_to_fcf", "Market Cap / FCF", "Valuation", "x", _safe_div(market_cap, free_cash_flow), "info/statements", "Market capitalization divided by free cash flow.")
    add_metric("earnings_yield", "Earnings Yield", "Valuation", "pct", _safe_div(net_income, market_cap), "info/statements", "Net income divided by market capitalization.")
    add_metric("fcf_yield", "FCF Yield", "Valuation", "pct", _safe_div(free_cash_flow, market_cap), "info/statements", "Free cash flow divided by market capitalization.")
    add_metric("dividend_yield", "Dividend Yield", "Valuation", "pct", dividend_yield, "info", "Trailing annual dividend yield.")

    add_metric("gross_margin", "Gross Margin", "Profitability", "pct", _safe_div(gross_profit, revenue), "income_statement", "Gross profit as a share of revenue.")
    add_metric("operating_margin", "Operating Margin", "Profitability", "pct", _safe_div(operating_income, revenue), "income_statement", "Operating income as a share of revenue.")
    add_metric("ebitda_margin", "EBITDA Margin", "Profitability", "pct", _safe_div(ebitda, revenue), "income_statement", "EBITDA as a share of revenue.")
    add_metric("net_margin", "Net Margin", "Profitability", "pct", _safe_div(net_income, revenue), "income_statement", "Net income as a share of revenue.")
    add_metric("fcf_margin", "FCF Margin", "Profitability", "pct", _safe_div(free_cash_flow, revenue), "cashflow/income_statement", "Free cash flow as a share of revenue.")
    add_metric("cfo_margin", "Operating Cash Flow Margin", "Profitability", "pct", _safe_div(operating_cash_flow, revenue), "cashflow/income_statement", "Operating cash flow as a share of revenue.")

    add_metric("roe", "Return on Equity", "Returns", "pct", _safe_div(net_income, avg_equity), "income_statement/balance_sheet", "Net income divided by average equity.")
    add_metric("roa", "Return on Assets", "Returns", "pct", _safe_div(net_income, avg_assets), "income_statement/balance_sheet", "Net income divided by average assets.")
    add_metric("roic", "Return on Invested Capital", "Returns", "pct", _safe_div(nopat, avg_invested_capital), "income_statement/balance_sheet", "NOPAT divided by average invested capital.")
    add_metric("asset_turnover", "Asset Turnover", "Efficiency", "x", _safe_div(revenue, avg_assets), "income_statement/balance_sheet", "Revenue divided by average assets.")
    add_metric("inventory_turnover", "Inventory Turnover", "Efficiency", "x", _safe_div(cost_of_revenue, avg_inventory), "income_statement/balance_sheet", "Cost of revenue divided by average inventory.")
    receivables_turnover = _safe_div(revenue, avg_receivables)
    add_metric("receivables_turnover", "Receivables Turnover", "Efficiency", "x", receivables_turnover, "income_statement/balance_sheet", "Revenue divided by average receivables.")
    add_metric("days_sales_outstanding", "Days Sales Outstanding", "Efficiency", "days", _safe_div(365.0, receivables_turnover), "income_statement/balance_sheet", "365 divided by receivables turnover.")
    inventory_turnover = _safe_div(cost_of_revenue, avg_inventory)
    add_metric("days_inventory_outstanding", "Days Inventory Outstanding", "Efficiency", "days", _safe_div(365.0, inventory_turnover), "income_statement/balance_sheet", "365 divided by inventory turnover.")

    add_metric("current_ratio", "Current Ratio", "Liquidity & Leverage", "x", _safe_div(current_assets, current_liabilities), "balance_sheet", "Current assets divided by current liabilities.")
    add_metric("quick_ratio", "Quick Ratio", "Liquidity & Leverage", "x", _safe_div(quick_assets, current_liabilities), "balance_sheet", "Quick assets divided by current liabilities.")
    add_metric("cash_ratio", "Cash Ratio", "Liquidity & Leverage", "x", _safe_div(cash_short, current_liabilities), "balance_sheet", "Cash and short-term investments divided by current liabilities.")
    add_metric("debt_to_equity", "Debt / Equity", "Liquidity & Leverage", "x", _safe_div(total_debt, total_equity), "balance_sheet", "Total debt divided by equity.")
    add_metric("debt_to_assets", "Debt / Assets", "Liquidity & Leverage", "pct", _safe_div(total_debt, total_assets), "balance_sheet", "Total debt divided by total assets.")
    add_metric("net_debt_to_ebitda", "Net Debt / EBITDA", "Liquidity & Leverage", "x", _safe_div(net_debt, ebitda), "balance_sheet/income_statement", "Net debt divided by EBITDA.")
    add_metric("interest_coverage", "Interest Coverage", "Liquidity & Leverage", "x", _safe_div(ebit, interest_expense), "income_statement", "EBIT divided by interest expense.")

    add_metric("fcf_conversion", "FCF Conversion", "Cash Flow Quality", "pct", _safe_div(free_cash_flow, net_income), "cashflow/income_statement", "Free cash flow divided by net income.")
    add_metric("capex_to_revenue", "Capex / Revenue", "Cash Flow Quality", "pct", _safe_div(abs(capex) if capex is not None else None, revenue), "cashflow/income_statement", "Absolute capex divided by revenue.")
    add_metric("payout_ratio", "Dividend Payout Ratio", "Cash Flow Quality", "pct", _safe_div(abs(dividends_paid) if dividends_paid is not None else None, net_income), "cashflow/income_statement", "Dividends paid divided by net income.")
    add_metric("buyback_yield", "Buyback Yield", "Cash Flow Quality", "pct", _safe_div(abs(buybacks) if buybacks is not None else None, market_cap), "cashflow/info", "Repurchases divided by market cap.")

    add_metric("revenue_growth_yoy", "Revenue Growth", "Growth", "pct", _safe_div(revenue - revenue_prev if revenue is not None and revenue_prev is not None else None, revenue_prev), "income_statement", "Latest period revenue growth versus prior period.")
    add_metric("net_income_growth_yoy", "Net Income Growth", "Growth", "pct", _safe_div(net_income - net_income_prev if net_income is not None and net_income_prev is not None else None, net_income_prev), "income_statement", "Latest period net income growth versus prior period.")
    add_metric("fcf_growth_yoy", "Free Cash Flow Growth", "Growth", "pct", _safe_div(free_cash_flow - free_cash_flow_prev if free_cash_flow is not None and free_cash_flow_prev is not None else None, free_cash_flow_prev), "cashflow", "Latest period free cash flow growth versus prior period.")
    add_metric("eps_growth_yoy", "Diluted EPS Growth", "Growth", "pct", _safe_div(diluted_eps - diluted_eps_prev if diluted_eps is not None and diluted_eps_prev is not None else None, diluted_eps_prev), "income_statement", "Latest period diluted EPS growth versus prior period.")
    add_metric("book_value_growth_yoy", "Book Equity Growth", "Growth", "pct", _safe_div(total_equity - total_equity_prev if total_equity is not None and total_equity_prev is not None else None, total_equity_prev), "balance_sheet", "Latest period total equity growth versus prior period.")

    return metrics


def _format_holders_label(raw: str) -> str:
    cleaned = raw.replace("_", " ")
    cleaned = re.sub(r"(?<!^)(?=[A-Z])", " ", cleaned)
    return " ".join(part.capitalize() for part in cleaned.split())


def _compute_total_return(history_df: Any) -> float | None:
    if not isinstance(history_df, pd.DataFrame) or history_df.empty:
        return None
    closes = history_df.get("Close")
    if closes is None:
        return None
    closes = pd.Series(closes).dropna()
    if len(closes) < 2:
        return None
    start_price = _as_float(closes.iloc[0])
    end_price = _as_float(closes.iloc[-1])
    if start_price is None or end_price is None or start_price <= 0:
        return None
    return end_price / start_price - 1.0


def _build_full_address(info: dict[str, Any]) -> str | None:
    parts = [
        _as_str(info.get("address1")),
        _as_str(info.get("address2")),
        _as_str(info.get("city")),
        _as_str(info.get("state")),
        _as_str(info.get("zip")),
        _as_str(info.get("country")),
    ]
    out = [part for part in parts if part]
    return ", ".join(out) if out else None


def _normalize_key(label: str) -> str:
    return label.strip().lower().replace(" ", "_")


def _parse_major_holders(df: Any, *, max_rows: int) -> list[YahooShareholderBreakdownRow]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []

    rows: list[tuple[str, Any]] = []
    work = df.copy()

    if "Breakdown" in work.columns and "Value" in work.columns:
        for _, row in work.head(max_rows).iterrows():
            rows.append((str(row.get("Breakdown")), row.get("Value")))
    elif work.shape[1] >= 2:
        first = str(work.columns[0])
        second = str(work.columns[1])
        for _, row in work.head(max_rows).iterrows():
            rows.append((str(row.get(first)), row.get(second)))
    else:
        series = work.iloc[:, 0]
        for idx, value in series.head(max_rows).items():
            rows.append((str(idx), value))

    out: list[YahooShareholderBreakdownRow] = []
    for raw_label, raw_value in rows:
        label = _format_holders_label(raw_label)
        value = _as_float(raw_value)
        display_value: str | None = None

        raw_str = _as_str(raw_value)
        if raw_str is not None and "%" in raw_str:
            display_value = raw_str
            if value is not None and value > 1:
                value = value / 100.0

        normalized = _normalize_key(raw_label)
        if value is not None and display_value is None:
            if "percent" in normalized:
                display_value = f"{value * 100:.2f}%"
            elif "count" in normalized:
                display_value = f"{int(round(value)):,}"
            else:
                display_value = f"{value:,.4f}"

        out.append(
            YahooShareholderBreakdownRow(
                label=label,
                value=value,
                display_value=display_value,
            )
        )
    return out


def _parse_institutional_holders(df: Any, *, max_rows: int) -> list[YahooInstitutionalHolderRow]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []

    work = df.copy()
    if not isinstance(work.index, pd.RangeIndex):
        work = work.reset_index()

    out: list[YahooInstitutionalHolderRow] = []
    for _, row in work.head(max_rows).iterrows():
        values: dict[str, Any] = {}
        for column in work.columns:
            key = _normalize_key(str(column))
            values[key] = row.get(column)

        holder = _as_str(values.get("holder"))
        if holder is None:
            continue

        out.append(
            YahooInstitutionalHolderRow(
                date_reported=_to_date(values.get("date_reported") or values.get("date")),
                holder=holder,
                pct_held=_as_float(values.get("pctheld") or values.get("pct_held")),
                shares=_as_float(values.get("shares")),
                value=_as_float(values.get("value")),
                pct_change=_as_float(values.get("pctchange") or values.get("pct_change")),
            )
        )
    return out


def _build_current_recommendations(
    recommendations_df: Any,
    recommendation_key: str | None,
) -> list[dict[str, Any]]:
    if not isinstance(recommendations_df, pd.DataFrame) or recommendations_df.empty:
        if recommendation_key:
            return [{"label": recommendation_key.title(), "count": 1}]
        return []

    work = recommendations_df.copy().reset_index()
    row: pd.Series | None = None
    period_cols = [col for col in work.columns if str(col).lower() == "period"]
    if period_cols:
        period_col = period_cols[0]
        mask = work[period_col].astype(str).str.strip().str.lower().isin({"0m", "current", "latest"})
        if mask.any():
            row = work[mask].iloc[0]
    if row is None and len(work) > 0:
        row = work.iloc[0]
    if row is None:
        return []

    buckets = [
        ("Strong Buy", "strongBuy"),
        ("Buy", "buy"),
        ("Hold", "hold"),
        ("Sell", "sell"),
        ("Strong Sell", "strongSell"),
    ]
    out: list[dict[str, Any]] = []
    for label, key in buckets:
        count = _as_int(row.get(key))
        if count is not None:
            out.append({"label": label, "count": max(count, 0)})
    if not out and recommendation_key:
        out.append({"label": recommendation_key.title(), "count": 1})
    return out


def _build_target_scenarios(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    current = _as_float(snapshot.get("current"))
    out: list[dict[str, Any]] = []
    for label, key in [
        ("Low", "low"),
        ("Median", "median"),
        ("Mean", "mean"),
        ("High", "high"),
    ]:
        target = _as_float(snapshot.get(key))
        ret = None
        if current is not None and current > 0 and target is not None:
            ret = target / current - 1.0
        out.append({"label": label, "target": target, "return_pct": ret})
    return out


def _normalize_period_label(value: Any) -> str:
    raw = _as_str(value)
    if raw is None:
        return ""
    return raw.strip().lower().replace(" ", "")


def _extract_period_estimate(
    frame: Any,
    *,
    period: str,
) -> dict[str, float | int | None]:
    out: dict[str, float | int | None] = {
        "avg": None,
        "low": None,
        "high": None,
        "number_of_analysts": None,
    }
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return out

    work = frame.copy().reset_index()
    period_col = str(work.columns[0]) if len(work.columns) > 0 else "period"
    target_norm = _normalize_period_label(period)
    if target_norm == "":
        return out

    match_row: pd.Series | None = None
    for _, row in work.iterrows():
        if _normalize_period_label(row.get(period_col)) == target_norm:
            match_row = row
            break
    if match_row is None:
        return out

    for col in work.columns:
        key = str(col).lower().replace(" ", "")
        if key == "avg":
            out["avg"] = _as_float(match_row.get(col))
        elif key == "low":
            out["low"] = _as_float(match_row.get(col))
        elif key == "high":
            out["high"] = _as_float(match_row.get(col))
        elif key in {"numberofanalysts", "analystcount"}:
            out["number_of_analysts"] = _as_int(match_row.get(col))
    return out


def fetch_forward_estimates(
    *,
    symbol: str,
) -> YahooForwardEstimateSnapshot:
    symbol = symbol.upper()
    ticker = yf.Ticker(symbol)
    warnings: list[str] = []

    try:
        earnings_estimate = ticker.earnings_estimate
    except Exception as exc:  # pragma: no cover - provider variability
        earnings_estimate = pd.DataFrame()
        warnings.append(f"earnings_estimate_fetch_failed:{exc.__class__.__name__}")

    try:
        revenue_estimate = ticker.revenue_estimate
    except Exception as exc:  # pragma: no cover - provider variability
        revenue_estimate = pd.DataFrame()
        warnings.append(f"revenue_estimate_fetch_failed:{exc.__class__.__name__}")

    fy0_rev = _extract_period_estimate(revenue_estimate, period="0y")
    fy1_rev = _extract_period_estimate(revenue_estimate, period="+1y")
    fy0_eps = _extract_period_estimate(earnings_estimate, period="0y")
    fy1_eps = _extract_period_estimate(earnings_estimate, period="+1y")

    has_core = any(
        [
            fy0_rev.get("avg") is not None,
            fy1_rev.get("avg") is not None,
            fy0_eps.get("avg") is not None,
            fy1_eps.get("avg") is not None,
        ]
    )
    status = "ok"
    if warnings:
        status = "partial"
    if not has_core:
        status = "no_data"
        warnings.append("forward_estimates:no_data")

    return YahooForwardEstimateSnapshot(
        symbol=symbol,
        as_of_date=date.today(),
        status=status,
        warnings=sorted(set(warnings)),
        fy0_revenue_avg=_as_float(fy0_rev.get("avg")),
        fy0_revenue_low=_as_float(fy0_rev.get("low")),
        fy0_revenue_high=_as_float(fy0_rev.get("high")),
        fy1_revenue_avg=_as_float(fy1_rev.get("avg")),
        fy1_revenue_low=_as_float(fy1_rev.get("low")),
        fy1_revenue_high=_as_float(fy1_rev.get("high")),
        fy0_eps_avg=_as_float(fy0_eps.get("avg")),
        fy0_eps_low=_as_float(fy0_eps.get("low")),
        fy0_eps_high=_as_float(fy0_eps.get("high")),
        fy1_eps_avg=_as_float(fy1_eps.get("avg")),
        fy1_eps_low=_as_float(fy1_eps.get("low")),
        fy1_eps_high=_as_float(fy1_eps.get("high")),
        revenue_analyst_count_fy0=_as_int(fy0_rev.get("number_of_analysts")),
        revenue_analyst_count_fy1=_as_int(fy1_rev.get("number_of_analysts")),
        eps_analyst_count_fy0=_as_int(fy0_eps.get("number_of_analysts")),
        eps_analyst_count_fy1=_as_int(fy1_eps.get("number_of_analysts")),
    )


def _extract_news_articles(raw_items: Any, *, symbol: str, max_rows: int) -> list[YahooNewsArticle]:
    if not isinstance(raw_items, list):
        return []

    articles: list[YahooNewsArticle] = []
    for item in raw_items[: max_rows * 2]:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, dict):
            content = {}

        article_id = _as_str(content.get("id")) or _as_str(item.get("id"))
        title = _as_str(content.get("title"))
        if title is None:
            continue

        summary = _as_str(content.get("summary")) or _as_str(content.get("description"))
        pub_date = _to_datetime(content.get("pubDate")) or _to_datetime(content.get("displayTime"))
        provider_dict = content.get("provider")
        provider = _as_str(provider_dict.get("displayName")) if isinstance(provider_dict, dict) else None

        click_through = content.get("clickThroughUrl")
        canonical = content.get("canonicalUrl")
        url = None
        if isinstance(click_through, dict):
            url = _as_str(click_through.get("url"))
        if url is None and isinstance(canonical, dict):
            url = _as_str(canonical.get("url"))
        if url is None:
            url = _as_str(content.get("previewUrl"))

        thumbnail_dict = content.get("thumbnail")
        thumbnail_url = _as_str(thumbnail_dict.get("originalUrl")) if isinstance(thumbnail_dict, dict) else None
        content_type = _as_str(content.get("contentType"))

        fallback_id = url or f"{symbol}-{title[:42]}"
        articles.append(
            YahooNewsArticle(
                id=article_id or fallback_id,
                title=title,
                summary=summary,
                pub_date=pub_date,
                provider=provider,
                url=url,
                thumbnail_url=thumbnail_url,
                content_type=content_type,
                symbols=[symbol],
            )
        )

    articles.sort(
        key=lambda article: (
            article.pub_date.timestamp() if article.pub_date is not None else 0.0,
            article.title,
        ),
        reverse=True,
    )
    return articles[:max_rows]


def fetch_security_news(
    *,
    symbol: str,
    max_rows: int = 40,
) -> YahooSecurityNewsPayload:
    symbol = symbol.upper()
    warnings: list[str] = []
    status = "ok"
    articles: list[YahooNewsArticle] = []

    try:
        ticker = yf.Ticker(symbol)
        raw_news = ticker.news
    except Exception as exc:  # pragma: no cover - provider variability
        raw_news = []
        warnings.append(f"news_fetch_failed:{exc.__class__.__name__}")

    articles = _extract_news_articles(raw_news, symbol=symbol, max_rows=max_rows)

    if warnings:
        status = "partial"
    if not articles:
        status = "no_data" if not warnings else "partial"

    return YahooSecurityNewsPayload(
        symbol=symbol,
        status=status,
        warnings=warnings,
        articles=articles,
    )


def fetch_portfolio_news(
    *,
    symbols: list[str],
    max_per_symbol: int = 25,
    max_rows: int = 250,
) -> YahooPortfolioNewsPayload:
    warnings: list[str] = []
    seen: dict[str, YahooNewsArticle] = {}

    clean_symbols = sorted({symbol.strip().upper() for symbol in symbols if symbol and symbol.strip()})
    for symbol in clean_symbols:
        payload = fetch_security_news(symbol=symbol, max_rows=max_per_symbol)
        if payload.warnings:
            warnings.extend([f"{symbol}:{warning}" for warning in payload.warnings])

        for article in payload.articles:
            dedupe_key = article.id or article.url or f"{article.title}-{article.pub_date}"
            existing = seen.get(dedupe_key)
            if existing is None:
                seen[dedupe_key] = article
            else:
                existing_symbols = set(existing.symbols)
                existing_symbols.update(article.symbols)
                existing.symbols = sorted(existing_symbols)

    articles = list(seen.values())
    articles.sort(
        key=lambda article: (
            article.pub_date.timestamp() if article.pub_date is not None else 0.0,
            article.title,
        ),
        reverse=True,
    )
    articles = articles[:max_rows]

    status = "ok"
    if warnings:
        status = "partial"
    if not articles:
        status = "no_data" if not warnings else "partial"

    return YahooPortfolioNewsPayload(
        status=status,
        warnings=sorted(set(warnings)),
        articles=articles,
    )


def fetch_stock_overview(
    *,
    symbol: str,
    max_holders: int = 60,
) -> YahooStockOverviewPayload:
    symbol = symbol.upper()
    ticker = yf.Ticker(symbol)
    warnings: list[str] = []

    info: dict[str, Any] = {}
    fast_info: dict[str, Any] = {}
    try:
        info = ticker.info or {}
    except Exception as exc:  # pragma: no cover - provider variability
        warnings.append(f"info_fetch_failed:{exc.__class__.__name__}")
        info = {}

    try:
        fast_info = dict(ticker.fast_info or {})
    except Exception as exc:  # pragma: no cover - provider variability
        warnings.append(f"fast_info_fetch_failed:{exc.__class__.__name__}")
        fast_info = {}

    current_price = _as_float(info.get("currentPrice"))
    if current_price is None:
        current_price = _as_float(fast_info.get("lastPrice"))

    daily_return: float | None = None
    ytd_return: float | None = None
    one_year_return: float | None = None

    try:
        recent_history = ticker.history(period="7d", auto_adjust=True)
        daily_return = _compute_total_return(recent_history.tail(2))
        if current_price is None:
            closes = recent_history.get("Close")
            if isinstance(closes, pd.Series):
                current_price = _as_float(closes.dropna().iloc[-1]) if len(closes.dropna()) > 0 else current_price
    except Exception as exc:  # pragma: no cover - provider variability
        warnings.append(f"daily_return_fetch_failed:{exc.__class__.__name__}")

    try:
        ytd_start = date.today().replace(month=1, day=1)
        ytd_history = ticker.history(
            start=ytd_start,
            end=date.today() + timedelta(days=1),
            auto_adjust=True,
        )
        ytd_return = _compute_total_return(ytd_history)
    except Exception as exc:  # pragma: no cover - provider variability
        warnings.append(f"ytd_return_fetch_failed:{exc.__class__.__name__}")

    try:
        one_year_history = ticker.history(period="1y", auto_adjust=True)
        one_year_return = _compute_total_return(one_year_history)
    except Exception as exc:  # pragma: no cover - provider variability
        warnings.append(f"one_year_return_fetch_failed:{exc.__class__.__name__}")

    try:
        major_holders_df = ticker.major_holders
    except Exception as exc:  # pragma: no cover - provider variability
        major_holders_df = pd.DataFrame()
        warnings.append(f"major_holders_fetch_failed:{exc.__class__.__name__}")

    try:
        institutional_holders_df = ticker.institutional_holders
    except Exception as exc:  # pragma: no cover - provider variability
        institutional_holders_df = pd.DataFrame()
        warnings.append(f"institutional_holders_fetch_failed:{exc.__class__.__name__}")

    shareholder_breakdown = _parse_major_holders(major_holders_df, max_rows=max_holders)
    institutional_holders = _parse_institutional_holders(institutional_holders_df, max_rows=max_holders)

    dividend_rate = _as_float(info.get("dividendRate")) or _as_float(info.get("trailingAnnualDividendRate"))
    dividend_yield = None
    if current_price is not None and current_price > 0 and dividend_rate is not None:
        dividend_yield = dividend_rate / current_price
    if dividend_yield is None:
        dividend_yield = _as_float(info.get("trailingAnnualDividendYield"))
    if dividend_yield is None:
        dividend_yield = _as_float(info.get("dividendYield"))
    if dividend_yield is not None and dividend_yield > 1:
        dividend_yield = dividend_yield / 100.0

    has_core_data = any(
        [
            _as_str(info.get("longName")) is not None,
            _as_str(info.get("longBusinessSummary")) is not None,
            current_price is not None,
            _as_float(info.get("marketCap")) is not None,
        ]
    )

    status = "ok"
    if warnings:
        status = "partial"
    if not has_core_data and not shareholder_breakdown and not institutional_holders:
        status = "no_data"

    return YahooStockOverviewPayload(
        symbol=symbol,
        status=status,
        warnings=sorted(set(warnings)),
        name=_as_str(info.get("longName")) or _as_str(info.get("shortName")),
        description=_as_str(info.get("longBusinessSummary")),
        industry=_as_str(info.get("industry")) or _as_str(info.get("industryDisp")),
        sector=_as_str(info.get("sector")) or _as_str(info.get("sectorDisp")),
        country=_as_str(info.get("country")),
        full_address=_build_full_address(info),
        website=_as_str(info.get("website")),
        market_cap=_as_float(info.get("marketCap")),
        current_price=current_price,
        daily_return=daily_return,
        ytd_return=ytd_return,
        one_year_return=one_year_return,
        beta=_as_float(info.get("beta")),
        pe=_as_float(info.get("trailingPE")),
        dividend_yield=dividend_yield,
        shareholder_breakdown=shareholder_breakdown,
        institutional_holders=institutional_holders,
    )


def fetch_financial_statements(
    *,
    symbol: str,
    max_rows: int = 220,
) -> YahooFinancialStatementsPayload:
    symbol = symbol.upper()
    ticker = yf.Ticker(symbol)
    warnings: list[str] = []

    def load_frame(attr: str) -> pd.DataFrame:
        try:
            frame = getattr(ticker, attr)
        except Exception as exc:  # pragma: no cover - provider variability
            warnings.append(f"{attr}_fetch_failed:{exc.__class__.__name__}")
            return pd.DataFrame()
        if isinstance(frame, pd.DataFrame):
            return frame
        return pd.DataFrame()

    income_annual = load_frame("incomestmt")
    income_quarterly = load_frame("quarterly_incomestmt")
    balance_annual = load_frame("balance_sheet")
    balance_quarterly = load_frame("quarterly_balance_sheet")
    cashflow_annual = load_frame("cashflow")
    cashflow_quarterly = load_frame("quarterly_cashflow")

    payload = YahooFinancialStatementsPayload(
        symbol=symbol,
        status="ok",
        warnings=sorted(set(warnings)),
        income_statement_annual=_statement_frame_to_rows(income_annual, max_rows=max_rows),
        income_statement_quarterly=_statement_frame_to_rows(income_quarterly, max_rows=max_rows),
        balance_sheet_annual=_statement_frame_to_rows(balance_annual, max_rows=max_rows),
        balance_sheet_quarterly=_statement_frame_to_rows(balance_quarterly, max_rows=max_rows),
        cashflow_annual=_statement_frame_to_rows(cashflow_annual, max_rows=max_rows),
        cashflow_quarterly=_statement_frame_to_rows(cashflow_quarterly, max_rows=max_rows),
    )

    has_any_rows = any(
        [
            len(payload.income_statement_annual) > 0,
            len(payload.income_statement_quarterly) > 0,
            len(payload.balance_sheet_annual) > 0,
            len(payload.balance_sheet_quarterly) > 0,
            len(payload.cashflow_annual) > 0,
            len(payload.cashflow_quarterly) > 0,
        ]
    )

    if payload.warnings:
        payload.status = "partial"
    if not has_any_rows:
        payload.status = "no_data"
        if "financials:no_data" not in payload.warnings:
            payload.warnings.append("financials:no_data")

    return payload


def fetch_financial_ratios(
    *,
    symbol: str,
) -> YahooFinancialRatiosPayload:
    symbol = symbol.upper()
    ticker = yf.Ticker(symbol)
    warnings: list[str] = []

    info: dict[str, Any] = {}
    fast_info: dict[str, Any] = {}
    try:
        info = ticker.info or {}
    except Exception as exc:  # pragma: no cover - provider variability
        info = {}
        warnings.append(f"info_fetch_failed:{exc.__class__.__name__}")

    try:
        fast_info = dict(ticker.fast_info or {})
    except Exception as exc:  # pragma: no cover - provider variability
        fast_info = {}
        warnings.append(f"fast_info_fetch_failed:{exc.__class__.__name__}")

    def load_frame(attr: str) -> pd.DataFrame:
        try:
            frame = getattr(ticker, attr)
        except Exception as exc:  # pragma: no cover - provider variability
            warnings.append(f"{attr}_fetch_failed:{exc.__class__.__name__}")
            return pd.DataFrame()
        if isinstance(frame, pd.DataFrame):
            return frame
        return pd.DataFrame()

    income_annual = load_frame("incomestmt")
    income_quarterly = load_frame("quarterly_incomestmt")
    balance_annual = load_frame("balance_sheet")
    balance_quarterly = load_frame("quarterly_balance_sheet")
    cashflow_annual = load_frame("cashflow")
    cashflow_quarterly = load_frame("quarterly_cashflow")

    annual_metrics = _compute_ratio_metrics(
        income_df=income_annual,
        balance_df=balance_annual,
        cashflow_df=cashflow_annual,
        info=info,
        fast_info=fast_info,
    )
    quarterly_metrics = _compute_ratio_metrics(
        income_df=income_quarterly,
        balance_df=balance_quarterly,
        cashflow_df=cashflow_quarterly,
        info=info,
        fast_info=fast_info,
    )

    has_any_values = any(
        metric.value is not None for metric in [*annual_metrics, *quarterly_metrics]
    )
    status = "ok"
    if warnings:
        status = "partial"
    if not has_any_values:
        status = "no_data"
        warnings.append("financial_ratios:no_data")

    return YahooFinancialRatiosPayload(
        symbol=symbol,
        status=status,
        warnings=sorted(set(warnings)),
        annual=annual_metrics,
        quarterly=quarterly_metrics,
    )


def fetch_security_events(
    *,
    symbol: str,
    start_date: date,
    end_date: date,
    max_rows: int = 250,
) -> YahooSecurityEventsPayload:
    symbol = symbol.upper()
    ticker = yf.Ticker(symbol)
    warnings: list[str] = []
    status = "ok"

    events: list[YahooMarketEvent] = []
    corporate_actions: list[YahooCorporateActionRow] = []
    insider_transactions: list[YahooInsiderTransactionRow] = []
    analyst_revisions: list[YahooAnalystRevisionRow] = []

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    try:
        actions = ticker.actions
    except Exception as exc:  # pragma: no cover - provider variability
        actions = pd.DataFrame()
        warnings.append(f"actions_fetch_failed:{exc.__class__.__name__}")

    if isinstance(actions, pd.DataFrame) and not actions.empty:
        actions_df = actions.copy().reset_index()
        date_col = _get_first_column(actions_df)
        for _, row in actions_df.iterrows():
            dt = _to_datetime(row.get(date_col))
            if dt is None:
                continue

            dividend = _as_float(row.get("Dividends")) or 0.0
            split = _as_float(row.get("Stock Splits")) or 0.0

            if dividend > 0:
                corporate_actions.append(
                    YahooCorporateActionRow(
                        date=dt,
                        action_type="dividend",
                        value=dividend,
                        description=f"Dividend payment {dividend:.4f}",
                    )
                )
                if start_dt <= dt <= end_dt:
                    events.append(
                        YahooMarketEvent(
                            id=f"div-{symbol}-{dt.isoformat()}",
                            date=dt,
                            event_type="dividend",
                            title="Dividend",
                            summary=f"Dividend {dividend:.4f}",
                            detail=f"{symbol} paid a dividend of {dividend:.4f} on {dt.date().isoformat()}",
                            link_target="corporate_actions",
                        )
                    )

            if split > 0:
                corporate_actions.append(
                    YahooCorporateActionRow(
                        date=dt,
                        action_type="stock_split",
                        value=split,
                        description=f"Stock split ratio {split:g}:1",
                    )
                )
                if start_dt <= dt <= end_dt:
                    events.append(
                        YahooMarketEvent(
                            id=f"split-{symbol}-{dt.isoformat()}",
                            date=dt,
                            event_type="stock_split",
                            title="Stock Split",
                            summary=f"Split ratio {split:g}:1",
                            detail=f"{symbol} stock split ratio {split:g}:1 on {dt.date().isoformat()}",
                            link_target="corporate_actions",
                        )
                    )

        corporate_actions.sort(key=lambda item: item.date, reverse=True)
        corporate_actions = corporate_actions[:max_rows]

    try:
        insider_df = ticker.insider_transactions
    except Exception as exc:  # pragma: no cover - provider variability
        insider_df = pd.DataFrame()
        warnings.append(f"insider_fetch_failed:{exc.__class__.__name__}")

    if isinstance(insider_df, pd.DataFrame) and not insider_df.empty:
        insider_reset = insider_df.copy().reset_index(drop=True).head(max_rows)
        for _, row in insider_reset.iterrows():
            date_val = (
                row.get("Start Date")
                or row.get("Transaction Start Date")
                or row.get("Date")
            )
            dt = _to_datetime(date_val)
            insider = _as_str(row.get("Insider"))
            transaction = _as_str(row.get("Transaction"))
            position = _as_str(row.get("Position"))
            shares = _as_float(row.get("Shares"))
            value = _as_float(row.get("Value"))
            ownership = _as_str(row.get("Ownership"))
            text = _as_str(row.get("Text"))

            insider_transactions.append(
                YahooInsiderTransactionRow(
                    date=dt,
                    insider=insider,
                    position=position,
                    transaction=transaction,
                    shares=shares,
                    value=value,
                    ownership=ownership,
                    text=text,
                )
            )

            if dt is not None and start_dt <= dt <= end_dt:
                shares_label = f"{shares:,.0f}" if shares is not None else "N/A"
                events.append(
                    YahooMarketEvent(
                        id=f"insider-{symbol}-{dt.isoformat()}-{insider or 'unknown'}",
                        date=dt,
                        event_type="insider_transaction",
                        title="Insider Transaction",
                        summary=f"{insider or 'Insider'} {transaction or 'transaction'} {shares_label} shares",
                        detail=text,
                        link_target="insider_transactions",
                    )
                )

    try:
        rev_df = ticker.upgrades_downgrades
    except Exception as exc:  # pragma: no cover - provider variability
        rev_df = pd.DataFrame()
        warnings.append(f"revisions_fetch_failed:{exc.__class__.__name__}")

    if isinstance(rev_df, pd.DataFrame) and not rev_df.empty:
        revisions = rev_df.copy().reset_index().head(max_rows)
        date_col = _get_first_column(revisions)
        for _, row in revisions.iterrows():
            dt = _to_datetime(row.get(date_col))
            if dt is None:
                continue
            firm = _as_str(row.get("Firm"))
            action = _as_str(row.get("Action"))
            to_grade = _as_str(row.get("ToGrade"))
            from_grade = _as_str(row.get("FromGrade"))
            cpt = _as_float(row.get("currentPriceTarget"))
            ppt = _as_float(row.get("priorPriceTarget"))
            pt_action = _as_str(row.get("priceTargetAction"))

            analyst_revisions.append(
                YahooAnalystRevisionRow(
                    date=dt,
                    firm=firm,
                    action=action,
                    to_grade=to_grade,
                    from_grade=from_grade,
                    current_price_target=cpt,
                    prior_price_target=ppt,
                    price_target_action=pt_action,
                )
            )

            if start_dt <= dt <= end_dt:
                summary = f"{firm or 'Firm'} {action or 'revision'}"
                if to_grade:
                    summary += f" to {to_grade}"
                events.append(
                    YahooMarketEvent(
                        id=f"rev-{symbol}-{dt.isoformat()}-{firm or 'unknown'}",
                        date=dt,
                        event_type="analyst_revision",
                        title="Analyst Revision",
                        summary=summary,
                        detail=f"From {from_grade or 'N/A'} to {to_grade or 'N/A'}"
                        + (f" | PT {ppt} -> {cpt}" if cpt is not None or ppt is not None else ""),
                        link_target="analyst_revisions",
                    )
                )

        analyst_revisions.sort(key=lambda item: item.date, reverse=True)
        analyst_revisions = analyst_revisions[:max_rows]

    events.sort(key=lambda item: item.date)

    if warnings:
        status = "partial"
    if not events and not corporate_actions and not insider_transactions and not analyst_revisions:
        status = "no_data"

    return YahooSecurityEventsPayload(
        symbol=symbol,
        status=status,
        warnings=warnings,
        events=events[: max_rows * 2],
        corporate_actions=corporate_actions,
        insider_transactions=insider_transactions[:max_rows],
        analyst_revisions=analyst_revisions,
    )


def fetch_analyst_detail(
    *,
    symbol: str,
    max_rows: int = 200,
) -> YahooAnalystDetailPayload:
    symbol = symbol.upper()
    ticker = yf.Ticker(symbol)
    warnings: list[str] = []

    snapshot_payload: dict[str, Any] = {
        "as_of_date": date.today(),
        "current": None,
        "high": None,
        "low": None,
        "mean": None,
        "median": None,
    }
    coverage_payload: dict[str, Any] = {
        "analyst_count": None,
        "recommendation_key": None,
        "recommendation_mean": None,
    }

    try:
        snap = fetch_security_snapshot(symbol, date.today())
        snapshot_payload["current"] = snap.current_price
        snapshot_payload["high"] = snap.target_high
        snapshot_payload["low"] = snap.target_low
        snapshot_payload["mean"] = snap.target_mean
        coverage_payload["analyst_count"] = snap.analyst_count
        coverage_payload["recommendation_key"] = snap.recommendation_key
        coverage_payload["recommendation_mean"] = snap.recommendation_mean
    except Exception as exc:  # pragma: no cover - provider variability
        warnings.append(f"snapshot_fetch_failed:{exc.__class__.__name__}")

    try:
        price_targets_raw = ticker.analyst_price_targets or {}
        if isinstance(price_targets_raw, dict):
            snapshot_payload["current"] = _as_float(price_targets_raw.get("current")) or snapshot_payload["current"]
            snapshot_payload["high"] = _as_float(price_targets_raw.get("high")) or snapshot_payload["high"]
            snapshot_payload["low"] = _as_float(price_targets_raw.get("low")) or snapshot_payload["low"]
            snapshot_payload["mean"] = _as_float(price_targets_raw.get("mean")) or snapshot_payload["mean"]
            snapshot_payload["median"] = _as_float(price_targets_raw.get("median")) or snapshot_payload["median"]
    except Exception as exc:  # pragma: no cover - provider variability
        warnings.append(f"price_targets_fetch_failed:{exc.__class__.__name__}")

    datasets: dict[str, list[dict[str, Any]]] = {
        "eps_trend": [],
        "eps_revisions": [],
        "earnings_estimate": [],
        "revenue_estimate": [],
        "growth_estimates": [],
        "recommendations_history": [],
    }
    recommendations_df: pd.DataFrame | Any = pd.DataFrame()

    dataset_specs: list[tuple[str, str]] = [
        ("eps_trend", "eps_trend"),
        ("eps_revisions", "eps_revisions"),
        ("earnings_estimate", "earnings_estimate"),
        ("revenue_estimate", "revenue_estimate"),
        ("growth_estimates", "growth_estimates"),
        ("recommendations_history", "recommendations"),
    ]
    for output_key, attr in dataset_specs:
        try:
            frame = getattr(ticker, attr)
            datasets[output_key] = _frame_to_rows(frame, max_rows=max_rows)
            if attr == "recommendations":
                recommendations_df = frame
        except Exception as exc:  # pragma: no cover - provider variability
            warnings.append(f"{attr}_fetch_failed:{exc.__class__.__name__}")
            datasets[output_key] = []

    current_recommendations = _build_current_recommendations(
        recommendations_df,
        _as_str(coverage_payload.get("recommendation_key")),
    )
    target_scenarios = _build_target_scenarios(snapshot_payload)

    status = "ok"
    has_core = any(
        [
            snapshot_payload.get("current") is not None,
            snapshot_payload.get("mean") is not None,
            len(datasets["recommendations_history"]) > 0,
            len(datasets["earnings_estimate"]) > 0,
            len(datasets["revenue_estimate"]) > 0,
        ]
    )
    if warnings:
        status = "partial"
    if not has_core:
        status = "no_data"

    return YahooAnalystDetailPayload(
        symbol=symbol,
        status=status,
        warnings=warnings,
        snapshot=snapshot_payload,
        coverage=coverage_payload,
        target_scenarios=target_scenarios,
        current_recommendations=current_recommendations,
        recommendations_history=datasets["recommendations_history"],
        recommendations_table=datasets["recommendations_history"],
        eps_trend=datasets["eps_trend"],
        eps_revisions=datasets["eps_revisions"],
        earnings_estimate=datasets["earnings_estimate"],
        revenue_estimate=datasets["revenue_estimate"],
        growth_estimates=datasets["growth_estimates"],
    )


def fetch_security_snapshot(symbol: str, as_of_date: date, retries: int = 2) -> YahooSecuritySnapshot:
    ticker = yf.Ticker(symbol)
    info: dict[str, Any] = {}
    fast_info: dict[str, Any] = {}

    last_exc: Exception | None = None
    for _ in range(max(1, retries + 1)):
        try:
            info = ticker.info or {}
            break
        except Exception as exc:  # pragma: no cover - network/provider behavior
            last_exc = exc
            info = {}
    for _ in range(max(1, retries + 1)):
        try:
            fast_info = dict(ticker.fast_info or {})
            break
        except Exception:  # pragma: no cover - network/provider behavior
            fast_info = {}

    if not info and not fast_info and last_exc is not None:
        raise last_exc

    current_price = _as_float(info.get("currentPrice"))
    if current_price is None:
        current_price = _as_float(fast_info.get("lastPrice"))
    if current_price is None:
        try:
            history = ticker.history(period="5d", auto_adjust=True)
            if not history.empty and "Close" in history.columns:
                current_price = _as_float(history["Close"].dropna().iloc[-1])
        except Exception:  # pragma: no cover - network/provider behavior
            current_price = None

    growth_proxy = _as_float(info.get("earningsGrowth"))
    if growth_proxy is None:
        growth_proxy = _as_float(info.get("revenueGrowth"))

    return YahooSecuritySnapshot(
        symbol=symbol.upper(),
        as_of_date=as_of_date,
        current_price=current_price,
        target_mean=_as_float(info.get("targetMeanPrice")),
        target_high=_as_float(info.get("targetHighPrice")),
        target_low=_as_float(info.get("targetLowPrice")),
        analyst_count=_as_int(info.get("numberOfAnalystOpinions")),
        recommendation_key=_as_str(info.get("recommendationKey")),
        recommendation_mean=_as_float(info.get("recommendationMean")),
        market_cap=_as_float(info.get("marketCap")),
        shares_outstanding=_as_float(info.get("sharesOutstanding")),
        free_cashflow=_as_float(info.get("freeCashflow")),
        trailing_eps=_as_float(info.get("trailingEps")),
        forward_eps=_as_float(info.get("forwardEps")),
        book_value_per_share=_as_float(info.get("bookValue")),
        roe=_as_float(info.get("returnOnEquity")),
        pe=_as_float(info.get("trailingPE")),
        forward_pe=_as_float(info.get("forwardPE")),
        pb=_as_float(info.get("priceToBook")),
        ev_ebitda=_as_float(info.get("enterpriseToEbitda")),
        sector=_as_str(info.get("sector")),
        industry=_as_str(info.get("industry")),
        growth_proxy=growth_proxy,
    )


def fetch_market_rate_snapshot(
    *,
    years: int = 5,
    market_symbol: str = "^GSPC",
    risk_free_symbol: str = "^TNX",
) -> YahooMarketRateSnapshot:
    warnings: list[str] = []
    as_of = date.today()
    market_symbol = market_symbol.upper()
    risk_free_symbol = risk_free_symbol.upper()
    start = as_of - timedelta(days=max(366, years * 366 + 31))
    end = as_of + timedelta(days=1)

    market_return_5y: float | None = None
    risk_free_rate: float | None = None
    observations = 0

    try:
        market_raw = yf.download(
            market_symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            progress=False,
            auto_adjust=True,
        )
    except Exception as exc:  # pragma: no cover - network/provider behavior
        market_raw = pd.DataFrame()
        warnings.append(f"market_fetch_failed:{exc.__class__.__name__}")

    market_close = _extract_close_series(market_raw, market_symbol)
    market_returns = market_close.pct_change().dropna()
    observations = int(len(market_returns))
    if observations >= 252:
        total_growth = float((1.0 + market_returns).prod())
        if total_growth > 0:
            market_return_5y = float(total_growth ** (252.0 / observations) - 1.0)
        else:
            warnings.append("market_growth_nonpositive")
    elif observations > 0:
        warnings.append("market_history_short")
    else:
        warnings.append("market_no_data")

    try:
        rate_raw = yf.download(
            risk_free_symbol,
            start=(as_of - timedelta(days=45)).isoformat(),
            end=end.isoformat(),
            progress=False,
            auto_adjust=False,
        )
    except Exception as exc:  # pragma: no cover - network/provider behavior
        rate_raw = pd.DataFrame()
        warnings.append(f"risk_free_fetch_failed:{exc.__class__.__name__}")

    rate_close = _extract_close_series(rate_raw, risk_free_symbol)
    if not rate_close.empty:
        latest_rate = _as_float(rate_close.iloc[-1])
        if latest_rate is not None:
            # ^TNX values are quoted in percentage points, so convert to decimal.
            risk_free_rate = latest_rate / 100.0 if latest_rate > 1.0 else latest_rate
    else:
        warnings.append("risk_free_no_data")

    erp_5y = None
    if market_return_5y is not None and risk_free_rate is not None:
        erp_5y = market_return_5y - risk_free_rate

    status = "ok"
    if warnings:
        status = "partial"
    if market_return_5y is None and risk_free_rate is None:
        status = "no_data"

    return YahooMarketRateSnapshot(
        as_of_date=as_of,
        status=status,
        warnings=warnings,
        market_symbol=market_symbol,
        risk_free_symbol=risk_free_symbol,
        market_return_5y=market_return_5y,
        risk_free_rate=risk_free_rate,
        erp_5y=erp_5y,
        observations=observations,
    )
