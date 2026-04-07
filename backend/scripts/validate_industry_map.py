from __future__ import annotations

import argparse
from collections import Counter
from typing import Iterable

from app.services.industry_map import INDUSTRY_MAP, IndustryMapEntry

COMMON_TYPOS: dict[str, str] = {
    "Alcholic": "Alcoholic",
    "Alchohol": "Alcohol",
    "Beverages - Alcholic": "Beverages - Alcoholic",
}


def validate_industry_map(entries: Iterable[IndustryMapEntry]) -> list[str]:
    data = list(entries)
    issues: list[str] = []

    slugs = [item.slug for item in data]
    displays = [item.display for item in data]

    duplicate_slugs = [slug for slug, count in Counter(slugs).items() if count > 1]
    if duplicate_slugs:
        issues.append(f"Duplicate slugs detected: {', '.join(sorted(duplicate_slugs))}")

    for idx, item in enumerate(data):
        if not item.slug or not item.display or not item.sector_bucket:
            issues.append(f"Entry #{idx} has missing required fields")

        if item.slug != item.slug.strip() or " " in item.slug:
            issues.append(f"Slug '{item.slug}' must be trimmed and space-free")

        for typo, correction in COMMON_TYPOS.items():
            if typo in item.display:
                issues.append(
                    f"Display '{item.display}' contains likely typo '{typo}'. Suggested: '{item.display.replace(typo, correction)}'"
                )

    duplicate_displays = [name for name, count in Counter(displays).items() if count > 1]
    if duplicate_displays:
        issues.append(
            "Duplicate displays detected (allowed only if intentional): "
            + ", ".join(sorted(duplicate_displays))
        )

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate backend industry map for quality issues.")
    parser.parse_args()

    issues = validate_industry_map(INDUSTRY_MAP)
    if issues:
        for issue in issues:
            print(f"[ERROR] {issue}")
        return 1

    print("Industry map validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
