from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import httpx

BASE_FORECAST_URL = "https://tradingeconomics.com/forecast"


@dataclass(frozen=True)
class ForecastSpec:
    index_pos: int
    mapping: dict[int, str]


FORECAST_SPECS: dict[str, ForecastSpec] = {
    "interest-rate": ForecastSpec(
        index_pos=0,
        mapping={0: "Country", 1: "Last", 3: "Q2/26", 4: "Q3/26", 5: "Q4/26", 6: "Q1/27"},
    ),
    "stock-market": ForecastSpec(
        index_pos=1,
        mapping={1: "Index", 2: "Last", 4: "Q2/26", 5: "Q3/26", 6: "Q4/26", 7: "Q1/27"},
    ),
    "currency": ForecastSpec(
        index_pos=1,
        mapping={1: "Currency Pair", 2: "Last", 4: "Q2/26", 5: "Q3/26", 6: "Q4/26", 7: "Q1/27"},
    ),
    "wages": ForecastSpec(
        index_pos=0,
        mapping={0: "Country", 1: "Last", 3: "Q2/26", 4: "Q3/26", 5: "Q4/26", 6: "Q1/27"},
    ),
    "unemployment-rate": ForecastSpec(
        index_pos=0,
        mapping={0: "Country", 1: "Last", 3: "Q2/26", 4: "Q3/26", 5: "Q4/26", 6: "Q1/27"},
    ),
    "gdp": ForecastSpec(
        index_pos=0,
        mapping={0: "Country", 1: "Last", 3: "2026", 4: "2027", 5: "2028"},
    ),
    "consumer-price-index-cpi": ForecastSpec(
        index_pos=0,
        mapping={0: "Country", 1: "Last", 3: "Q2/26", 4: "Q3/26", 5: "Q4/26", 6: "Q1/27"},
    ),
    "inflation-rate": ForecastSpec(
        index_pos=0,
        mapping={0: "Country", 1: "Last", 3: "Q2/26", 4: "Q3/26", 5: "Q4/26", 6: "Q1/27"},
    ),
    "consumer-confidence": ForecastSpec(
        index_pos=0,
        mapping={0: "Country", 1: "Last", 3: "Q2/26", 4: "Q3/26", 5: "Q4/26", 6: "Q1/27"},
    ),
    "business-confidence": ForecastSpec(
        index_pos=0,
        mapping={0: "Country", 1: "Last", 3: "Q2/26", 4: "Q3/26", 5: "Q4/26", 6: "Q1/27"},
    ),
    "balance-of-trade": ForecastSpec(
        index_pos=0,
        mapping={0: "Country", 1: "Last", 3: "Q2/26", 4: "Q3/26", 5: "Q4/26", 6: "Q1/27"},
    ),
    "corporate-profits": ForecastSpec(
        index_pos=0,
        mapping={0: "Country", 1: "Last", 3: "Q2/26", 4: "Q3/26", 5: "Q4/26", 6: "Q1/27"},
    ),
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/115.0.0.0 Safari/537.36"
    )
}


def _to_safe_string(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def scrape_forecast(endpoint: str, spec: ForecastSpec) -> tuple[list[str], list[dict[str, str]]]:
    url = f"{BASE_FORECAST_URL}/{endpoint}"
    response = httpx.get(url, headers=HEADERS, timeout=15.0)
    response.raise_for_status()

    tables = pd.read_html(response.text)
    if not tables:
        raise RuntimeError(f"No table on page {url}")

    table = tables[0]
    mapping = spec.mapping
    selected = sorted(mapping.keys())
    missing = [idx for idx in selected if idx >= table.shape[1]]
    if missing:
        raise RuntimeError(f"Table format changed for endpoint '{endpoint}'; missing columns {missing}")

    parsed_rows: list[dict[str, str]] = []
    for _, row in table.iterrows():
        parsed_rows.append({mapping[idx]: _to_safe_string(row.iloc[idx]) for idx in selected})

    index_col = mapping[spec.index_pos]
    parsed_rows = [row for row in parsed_rows if row.get(index_col)]

    ordered_columns = [mapping[idx] for idx in selected]
    return ordered_columns, parsed_rows


def load_forecasts() -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {}
    for endpoint, spec in FORECAST_SPECS.items():
        columns, rows = scrape_forecast(endpoint, spec)
        payload[endpoint.replace("-", "_").title()] = {
            "columns": columns,
            "rows": rows,
        }
    return payload
