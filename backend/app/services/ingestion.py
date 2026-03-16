from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO, StringIO
from typing import Any

import pandas as pd
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models import HoldingsPosition, HoldingsSnapshot, PortfolioUpload
from app.services.pricing import get_latest_close


@dataclass
class ParsedRow:
    symbol: str
    units: float | None
    market_value: float | None
    cost_basis: float | None
    currency: str
    name: str | None
    asset_type: str | None


@dataclass
class IngestionResult:
    upload_id: int
    status: str
    accepted_rows: int
    rejected_rows: int
    unknown_tickers: list[str]
    missing_fields: list[str]
    errors: list[str] = field(default_factory=list)
    snapshot_id: int | None = None
    as_of_date: date | None = None


_COLUMN_ALIASES = {
    "symbol": ["ticker", "symbol", "identifier", "security", "isin"],
    "units": ["units", "quantity", "shares"],
    "market_value": ["market_value", "market value", "value", "notional", "mv"],
    "cost_basis": ["cost_basis", "cost basis", "cost"],
    "currency": ["currency", "ccy"],
    "name": ["name", "security_name", "security name"],
    "asset_type": ["asset_type", "asset class", "asset_class", "type"],
}


_REJECTION_REASON_LABELS = {
    "missing_symbol": "missing ticker/symbol",
    "missing_units_or_market_value": "missing both units and market value",
    "unknown_ticker_no_price": "ticker had no price in cache/provider",
    "non_positive_market_value": "market value was <= 0",
    "non_positive_total_market_value": "total market value was <= 0",
}


def _standardize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = {c: str(c).replace("\ufeff", "").strip().lower() for c in frame.columns}
    frame = frame.rename(columns=normalized)

    remap: dict[str, str] = {}
    for target, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in frame.columns:
                remap[alias] = target
                break

    frame = frame.rename(columns=remap)
    return frame


def _parse_upload_frame(file: UploadFile, payload: bytes) -> pd.DataFrame:
    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()

    if filename.endswith(".xlsx") or filename.endswith(".xls"):
        return pd.read_excel(BytesIO(payload), engine="openpyxl")

    # Accept extension-less and text/plain uploads from browser file pickers.
    is_text_like = filename.endswith(".csv") or filename.endswith(".tsv") or content_type in {
        "text/csv",
        "application/csv",
        "text/plain",
        "application/vnd.ms-excel",
    }
    if is_text_like:
        text = payload.decode("utf-8-sig", errors="replace")
        if not text.strip():
            raise ValueError("Empty file")

        sample = text[:8192]
        # Fast path for tab-delimited "CSV" exports.
        if "\t" in sample and sample.count("\t") >= sample.count(","):
            return pd.read_csv(StringIO(text), sep="\t")

        try:
            frame = pd.read_csv(StringIO(text), sep=None, engine="python")
        except Exception as exc:
            raise ValueError(f"Could not parse delimited text file: {exc}") from exc

        if frame.shape[1] == 1 and "\t" in sample:
            return pd.read_csv(StringIO(text), sep="\t")
        return frame

    raise ValueError("Unsupported file format. Upload CSV or XLSX.")


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _extract_rows(frame: pd.DataFrame) -> tuple[list[ParsedRow], int, list[str], Counter[str]]:
    frame = _standardize_columns(frame)

    missing_fields: list[str] = []
    if "symbol" not in frame.columns:
        missing_fields.append("ticker/symbol")
    if "units" not in frame.columns and "market_value" not in frame.columns:
        missing_fields.append("units or market_value")

    reason_counts: Counter[str] = Counter()
    if missing_fields:
        return [], len(frame.index), missing_fields, reason_counts

    accepted: list[ParsedRow] = []
    rejected = 0

    for _, row in frame.iterrows():
        symbol_raw = str(row.get("symbol", "")).strip().upper()
        if not symbol_raw or symbol_raw in {"NAN", "NONE"}:
            rejected += 1
            reason_counts["missing_symbol"] += 1
            continue

        units = _as_float(row.get("units"))
        market_value = _as_float(row.get("market_value"))
        if units is None and market_value is None:
            rejected += 1
            reason_counts["missing_units_or_market_value"] += 1
            continue

        accepted.append(
            ParsedRow(
                symbol=symbol_raw,
                units=units,
                market_value=market_value,
                cost_basis=_as_float(row.get("cost_basis")),
                currency=str(row.get("currency", "USD") or "USD").upper(),
                name=None if pd.isna(row.get("name")) else str(row.get("name")).strip() or None,
                asset_type=None if pd.isna(row.get("asset_type")) else str(row.get("asset_type")).strip() or None,
            )
        )

    return accepted, rejected, missing_fields, reason_counts


def _build_error_messages(
    *,
    missing_fields: list[str],
    unknown_tickers: list[str],
    reason_counts: Counter[str],
) -> list[str]:
    errors: list[str] = []

    if missing_fields:
        errors.append(
            "Missing required columns: "
            + ", ".join(missing_fields)
            + ". Ensure the file has ticker/symbol and units or market_value."
        )

    for reason_key, count in sorted(reason_counts.items()):
        if count <= 0:
            continue
        reason_label = _REJECTION_REASON_LABELS.get(reason_key, reason_key.replace("_", " "))
        errors.append(f"{count} row(s) rejected: {reason_label}.")

    unique_unknown = sorted(set(unknown_tickers))
    if unique_unknown:
        preview = ", ".join(unique_unknown[:8])
        suffix = "..." if len(unique_unknown) > 8 else ""
        errors.append(
            f"{len(unique_unknown)} ticker(s) could not be priced and were rejected: {preview}{suffix}."
        )

    return errors


def _aggregate_rows(rows: list[ParsedRow]) -> list[ParsedRow]:
    grouped: dict[str, ParsedRow] = {}

    for row in rows:
        existing = grouped.get(row.symbol)
        if existing is None:
            grouped[row.symbol] = ParsedRow(
                symbol=row.symbol,
                units=row.units,
                market_value=row.market_value,
                cost_basis=row.cost_basis,
                currency=row.currency,
                name=row.name,
                asset_type=row.asset_type,
            )
            continue

        existing.units = (existing.units or 0.0) + (row.units or 0.0)
        existing.market_value = (existing.market_value or 0.0) + (row.market_value or 0.0)

        if existing.cost_basis is None:
            existing.cost_basis = row.cost_basis
        elif row.cost_basis is not None:
            existing.cost_basis = (existing.cost_basis + row.cost_basis) / 2.0

        if not existing.name and row.name:
            existing.name = row.name
        if not existing.asset_type and row.asset_type:
            existing.asset_type = row.asset_type

    return list(grouped.values())


def _persist_rows(
    db: Session,
    *,
    portfolio_id: int,
    upload_row: PortfolioUpload,
    parsed_rows: list[ParsedRow],
    rejected_rows: int,
    missing_fields: list[str],
    reason_counts: Counter[str],
) -> IngestionResult:
    if missing_fields:
        upload_row.status = "failed"
        db.commit()
        return IngestionResult(
            upload_id=upload_row.id,
            status=upload_row.status,
            accepted_rows=0,
            rejected_rows=rejected_rows,
            unknown_tickers=[],
            missing_fields=missing_fields,
            errors=_build_error_messages(
                missing_fields=missing_fields,
                unknown_tickers=[],
                reason_counts=reason_counts,
            ),
        )

    aggregated = _aggregate_rows(parsed_rows)
    unknown_tickers: list[str] = []
    valid_rows: list[ParsedRow] = []

    for row in aggregated:
        market_value = row.market_value
        if market_value is None:
            if row.units is None:
                rejected_rows += 1
                continue
            px = get_latest_close(db, row.symbol)
            if px is None:
                unknown_tickers.append(row.symbol)
                rejected_rows += 1
                reason_counts["unknown_ticker_no_price"] += 1
                continue
            market_value = row.units * px

        if market_value <= 0:
            rejected_rows += 1
            reason_counts["non_positive_market_value"] += 1
            continue

        row.market_value = float(market_value)
        valid_rows.append(row)

    if not valid_rows:
        upload_row.status = "failed"
        db.commit()
        return IngestionResult(
            upload_id=upload_row.id,
            status=upload_row.status,
            accepted_rows=0,
            rejected_rows=rejected_rows,
            unknown_tickers=sorted(set(unknown_tickers)),
            missing_fields=[],
            errors=_build_error_messages(
                missing_fields=[],
                unknown_tickers=unknown_tickers,
                reason_counts=reason_counts,
            ),
        )

    total_value = sum(r.market_value or 0.0 for r in valid_rows)
    if total_value <= 0:
        reason_counts["non_positive_total_market_value"] += 1
        upload_row.status = "failed"
        db.commit()
        return IngestionResult(
            upload_id=upload_row.id,
            status=upload_row.status,
            accepted_rows=0,
            rejected_rows=rejected_rows,
            unknown_tickers=sorted(set(unknown_tickers)),
            missing_fields=["total market_value must be > 0"],
            errors=_build_error_messages(
                missing_fields=["total market_value must be > 0"],
                unknown_tickers=unknown_tickers,
                reason_counts=reason_counts,
            ),
        )

    snapshot = HoldingsSnapshot(
        portfolio_id=portfolio_id,
        as_of_date=date.today(),
        upload_id=upload_row.id,
    )
    db.add(snapshot)
    db.flush()

    for row in valid_rows:
        weight = (row.market_value or 0.0) / total_value
        db.add(
            HoldingsPosition(
                snapshot_id=snapshot.id,
                symbol=row.symbol,
                name=row.name,
                asset_type=row.asset_type,
                units=row.units,
                market_value=float(row.market_value or 0.0),
                cost_basis=row.cost_basis,
                currency=row.currency,
                weight=float(weight),
            )
        )

    upload_row.status = "completed"
    db.commit()

    return IngestionResult(
        upload_id=upload_row.id,
        status=upload_row.status,
        accepted_rows=len(valid_rows),
        rejected_rows=rejected_rows,
        unknown_tickers=sorted(set(unknown_tickers)),
        missing_fields=[],
        errors=_build_error_messages(
            missing_fields=[],
            unknown_tickers=unknown_tickers,
            reason_counts=reason_counts,
        ),
        snapshot_id=snapshot.id,
        as_of_date=snapshot.as_of_date,
    )


def ingest_holdings_upload(db: Session, portfolio_id: int, upload: UploadFile) -> IngestionResult:
    upload_row = PortfolioUpload(
        portfolio_id=portfolio_id,
        filename=upload.filename or "upload.csv",
        source="upload",
        status="processing",
    )
    db.add(upload_row)
    db.flush()

    payload = upload.file.read()
    if not payload:
        upload_row.status = "failed"
        db.commit()
        return IngestionResult(
            upload_id=upload_row.id,
            status=upload_row.status,
            accepted_rows=0,
            rejected_rows=0,
            unknown_tickers=[],
            missing_fields=["empty file"],
            errors=["File is empty. Upload a CSV/XLSX with header row and holdings data."],
        )

    try:
        frame = _parse_upload_frame(upload, payload)
    except Exception as exc:
        upload_row.status = "failed"
        db.commit()
        return IngestionResult(
            upload_id=upload_row.id,
            status=upload_row.status,
            accepted_rows=0,
            rejected_rows=0,
            unknown_tickers=[],
            missing_fields=[str(exc)],
            errors=[f"Could not parse upload file: {exc}"],
        )

    parsed_rows, rejected_rows, missing_fields, reason_counts = _extract_rows(frame)
    return _persist_rows(
        db,
        portfolio_id=portfolio_id,
        upload_row=upload_row,
        parsed_rows=parsed_rows,
        rejected_rows=rejected_rows,
        missing_fields=missing_fields,
        reason_counts=reason_counts,
    )


def ingest_manual_holdings(
    db: Session,
    *,
    portfolio_id: int,
    holdings: list[dict[str, Any]],
) -> IngestionResult:
    upload_row = PortfolioUpload(
        portfolio_id=portfolio_id,
        filename="manual-entry",
        source="manual",
        status="processing",
    )
    db.add(upload_row)
    db.flush()

    if not holdings:
        upload_row.status = "failed"
        db.commit()
        return IngestionResult(
            upload_id=upload_row.id,
            status=upload_row.status,
            accepted_rows=0,
            rejected_rows=0,
            unknown_tickers=[],
            missing_fields=["holdings list is empty"],
        )

    parsed_rows: list[ParsedRow] = []
    rejected_rows = 0
    reason_counts: Counter[str] = Counter()

    for item in holdings:
        symbol_raw = str(item.get("ticker") or item.get("symbol") or "").strip().upper()
        if not symbol_raw:
            rejected_rows += 1
            reason_counts["missing_symbol"] += 1
            continue

        units = _as_float(item.get("units"))
        market_value = _as_float(item.get("market_value"))
        if units is None and market_value is None:
            rejected_rows += 1
            reason_counts["missing_units_or_market_value"] += 1
            continue

        parsed_rows.append(
            ParsedRow(
                symbol=symbol_raw,
                units=units,
                market_value=market_value,
                cost_basis=_as_float(item.get("cost_basis")),
                currency=str(item.get("currency") or "USD").upper(),
                name=(str(item.get("name")).strip() or None) if item.get("name") is not None else None,
                asset_type=(str(item.get("asset_type")).strip() or None)
                if item.get("asset_type") is not None
                else None,
            )
        )

    return _persist_rows(
        db,
        portfolio_id=portfolio_id,
        upload_row=upload_row,
        parsed_rows=parsed_rows,
        rejected_rows=rejected_rows,
        missing_fields=[],
        reason_counts=reason_counts,
    )
