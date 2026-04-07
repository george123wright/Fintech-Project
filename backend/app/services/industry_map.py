from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class IndustryMapEntry:
    slug: str
    display: str
    sector_bucket: str


# Versioned so changes can be diffed, tested, and consumed deterministically.
INDUSTRY_MAP_VERSION: Final[str] = "2026-04-07"

# Keep slug and display values as first-class fields.
INDUSTRY_MAP: Final[tuple[IndustryMapEntry, ...]] = (
    IndustryMapEntry(slug="agricultural-inputs", display="Agricultural Inputs", sector_bucket="Basic Materials"),
    IndustryMapEntry(slug="aluminum", display="Aluminum", sector_bucket="Basic Materials"),
    IndustryMapEntry(slug="building-materials", display="Building Materials", sector_bucket="Basic Materials"),
    IndustryMapEntry(slug="chemicals", display="Chemicals", sector_bucket="Basic Materials"),
    IndustryMapEntry(slug="coking-coal", display="Coking Coal", sector_bucket="Basic Materials"),
    IndustryMapEntry(slug="gold", display="Gold", sector_bucket="Basic Materials"),
    IndustryMapEntry(slug="lumber-wood-production", display="Lumber & Wood Production", sector_bucket="Basic Materials"),
    IndustryMapEntry(slug="oil-gas-e-p", display="Oil & Gas E&P", sector_bucket="Energy"),
    IndustryMapEntry(slug="oil-gas-integrated", display="Oil & Gas Integrated", sector_bucket="Energy"),
    IndustryMapEntry(slug="oil-gas-midstream", display="Oil & Gas Midstream", sector_bucket="Energy"),
    IndustryMapEntry(slug="solar", display="Solar", sector_bucket="Energy"),
    IndustryMapEntry(slug="auto-manufacturers", display="Auto Manufacturers", sector_bucket="Consumer Discretionary"),
    IndustryMapEntry(slug="consumer-electronics", display="Consumer Electronics", sector_bucket="Consumer Discretionary"),
    IndustryMapEntry(slug="footwear-accessories", display="Footwear & Accessories", sector_bucket="Consumer Discretionary"),
    IndustryMapEntry(slug="internet-retail", display="Internet Retail", sector_bucket="Consumer Discretionary"),
    IndustryMapEntry(slug="resorts-casinos", display="Resorts & Casinos", sector_bucket="Consumer Discretionary"),
    IndustryMapEntry(slug="restaurants", display="Restaurants", sector_bucket="Consumer Discretionary"),
    IndustryMapEntry(slug="beverages-alcoholic", display="Beverages - Alcoholic", sector_bucket="Consumer Staples"),
    IndustryMapEntry(slug="beverages-non-alcoholic", display="Beverages - Non-Alcoholic", sector_bucket="Consumer Staples"),
    IndustryMapEntry(slug="discount-stores", display="Discount Stores", sector_bucket="Consumer Staples"),
    IndustryMapEntry(slug="food-distribution", display="Food Distribution", sector_bucket="Consumer Staples"),
    IndustryMapEntry(slug="household-personal-products", display="Household & Personal Products", sector_bucket="Consumer Staples"),
    IndustryMapEntry(slug="drug-manufacturers-general", display="Drug Manufacturers - General", sector_bucket="Healthcare"),
    IndustryMapEntry(slug="healthcare-plans", display="Healthcare Plans", sector_bucket="Healthcare"),
    IndustryMapEntry(slug="medical-devices", display="Medical Devices", sector_bucket="Healthcare"),
    IndustryMapEntry(slug="biotechnology", display="Biotechnology", sector_bucket="Healthcare"),
    IndustryMapEntry(slug="banks-diversified", display="Banks - Diversified", sector_bucket="Financials"),
    IndustryMapEntry(slug="capital-markets", display="Capital Markets", sector_bucket="Financials"),
    IndustryMapEntry(slug="credit-services", display="Credit Services", sector_bucket="Financials"),
    IndustryMapEntry(slug="financial-data-stock-exchanges", display="Financial Data & Stock Exchanges", sector_bucket="Financials"),
    IndustryMapEntry(slug="insurance-diversified", display="Insurance - Diversified", sector_bucket="Financials"),
    IndustryMapEntry(slug="asset-management", display="Asset Management", sector_bucket="Financials"),
    IndustryMapEntry(slug="aerospace-defense", display="Aerospace & Defense", sector_bucket="Industrials"),
    IndustryMapEntry(slug="specialty-industrial-machinery", display="Specialty Industrial Machinery", sector_bucket="Industrials"),
    IndustryMapEntry(slug="railroads", display="Railroads", sector_bucket="Industrials"),
    IndustryMapEntry(slug="integrated-freight-logistics", display="Integrated Freight & Logistics", sector_bucket="Industrials"),
    IndustryMapEntry(slug="engineering-construction", display="Engineering & Construction", sector_bucket="Industrials"),
    IndustryMapEntry(slug="consulting-services", display="Consulting Services", sector_bucket="Industrials"),
    IndustryMapEntry(slug="software-infrastructure", display="Software - Infrastructure", sector_bucket="Technology"),
    IndustryMapEntry(slug="software-application", display="Software - Application", sector_bucket="Technology"),
    IndustryMapEntry(slug="semiconductors", display="Semiconductors", sector_bucket="Technology"),
    IndustryMapEntry(slug="communication-equipment", display="Communication Equipment", sector_bucket="Technology"),
    IndustryMapEntry(slug="information-technology-services", display="Information Technology Services", sector_bucket="Technology"),
    IndustryMapEntry(slug="telecom-services", display="Telecom Services", sector_bucket="Communication Services"),
    IndustryMapEntry(slug="internet-content-information", display="Internet Content & Information", sector_bucket="Communication Services"),
    IndustryMapEntry(slug="entertainment", display="Entertainment", sector_bucket="Communication Services"),
    IndustryMapEntry(slug="broadcasting", display="Broadcasting", sector_bucket="Communication Services"),
    IndustryMapEntry(slug="utilities-regulated-electric", display="Utilities - Regulated Electric", sector_bucket="Utilities"),
    IndustryMapEntry(slug="utilities-diversified", display="Utilities - Diversified", sector_bucket="Utilities"),
    IndustryMapEntry(slug="utilities-renewable", display="Utilities - Renewable", sector_bucket="Utilities"),
    IndustryMapEntry(slug="reit-industrial", display="REIT - Industrial", sector_bucket="Real Estate"),
    IndustryMapEntry(slug="reit-retail", display="REIT - Retail", sector_bucket="Real Estate"),
    IndustryMapEntry(slug="reit-residential", display="REIT - Residential", sector_bucket="Real Estate"),
    IndustryMapEntry(slug="reit-healthcare-facilities", display="REIT - Healthcare Facilities", sector_bucket="Real Estate"),
)


def slug_to_display() -> dict[str, str]:
    return {entry.slug: entry.display for entry in INDUSTRY_MAP}


def display_to_slugs() -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for entry in INDUSTRY_MAP:
        mapping.setdefault(entry.display, []).append(entry.slug)
    return {display: sorted(slugs) for display, slugs in mapping.items()}


def slug_to_sector_bucket() -> dict[str, str]:
    return {entry.slug: entry.sector_bucket for entry in INDUSTRY_MAP}


def sector_bucket_to_slugs() -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for entry in INDUSTRY_MAP:
        mapping.setdefault(entry.sector_bucket, []).append(entry.slug)
    return {bucket: sorted(slugs) for bucket, slugs in mapping.items()}
