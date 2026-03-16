from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import csv
import io

from app.config import settings


@dataclass
class FredObservation:
    series_id: str
    observation_date: date
    value: float


def fetch_fred_series(
    *,
    series_id: str,
    start_date: date,
    end_date: date,
) -> list[FredObservation]:
    params: dict[str, str] = {
        "series_id": series_id,
        "observation_start": start_date.isoformat(),
        "observation_end": end_date.isoformat(),
        "file_type": "json",
    }
    if settings.fred_api_key:
        params["api_key"] = settings.fred_api_key

    url = f"{settings.fred_base_url.rstrip('/')}/series/observations?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "quick-balance/1.0"})
    try:
        with urlopen(req, timeout=settings.fred_timeout_sec) as response:  # nosec B310
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    except Exception:
        # Fallback endpoint that often works without API-key configuration.
        csv_url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        csv_req = Request(csv_url, headers={"User-Agent": "quick-balance/1.0"})
        with urlopen(csv_req, timeout=settings.fred_timeout_sec) as response:  # nosec B310
            text = response.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        out_csv: list[FredObservation] = []
        for row in reader:
            d_raw = row.get("DATE")
            v_raw = row.get(series_id)
            if d_raw in {None, ""} or v_raw in {None, "", "."}:
                continue
            try:
                obs_date = date.fromisoformat(str(d_raw))
            except ValueError:
                continue
            if obs_date < start_date or obs_date > end_date:
                continue
            try:
                val = float(v_raw)
            except (TypeError, ValueError):
                continue
            out_csv.append(FredObservation(series_id=series_id, observation_date=obs_date, value=val))
        return out_csv

    raw_obs = payload.get("observations", [])
    if not isinstance(raw_obs, list):
        return []

    out: list[FredObservation] = []
    for row in raw_obs:
        if not isinstance(row, dict):
            continue
        date_raw = row.get("date")
        value_raw = row.get("value")
        if not isinstance(date_raw, str):
            continue
        if value_raw in {None, ".", ""}:
            continue
        try:
            obs_date = date.fromisoformat(date_raw)
            value = float(value_raw)
        except (ValueError, TypeError):
            continue
        out.append(FredObservation(series_id=series_id, observation_date=obs_date, value=value))
    return out
