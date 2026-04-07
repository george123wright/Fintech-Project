from __future__ import annotations

from app.services.industry_map import (
    INDUSTRY_MAP,
    INDUSTRY_MAP_VERSION,
    display_to_slugs,
    sector_bucket_to_slugs,
    slug_to_display,
    slug_to_sector_bucket,
)
from scripts.validate_industry_map import validate_industry_map


def test_industry_map_has_version_and_entries() -> None:
    assert INDUSTRY_MAP_VERSION
    assert INDUSTRY_MAP


def test_reverse_lookup_helpers() -> None:
    by_slug = slug_to_display()
    by_display = display_to_slugs()

    assert by_slug["oil-gas-e-p"] == "Oil & Gas E&P"
    assert by_display["Oil & Gas E&P"] == ["oil-gas-e-p"]


def test_sector_bucket_helpers() -> None:
    sector_by_slug = slug_to_sector_bucket()
    slugs_by_bucket = sector_bucket_to_slugs()

    assert sector_by_slug["banks-diversified"] == "Financials"
    assert "banks-diversified" in slugs_by_bucket["Financials"]


def test_validator_passes_for_curated_map() -> None:
    issues = validate_industry_map(INDUSTRY_MAP)
    assert issues == []


def test_validator_flags_obvious_typo() -> None:
    broken = list(INDUSTRY_MAP)
    first = broken[0]
    broken[0] = type(first)(
        slug=first.slug,
        display="Beverages - Alcholic",
        sector_bucket=first.sector_bucket,
    )

    issues = validate_industry_map(broken)
    assert any("Beverages - Alcoholic" in issue for issue in issues)
