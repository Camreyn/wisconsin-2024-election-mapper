"""Validate generated election data used by the static app."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

EXPECTED_TOTALS = {
    "trump": 1_697_626,
    "harris": 1_668_229,
    "other": 57_063,
    "total": 3_422_918,
}
EXPECTED_SENATE_TOTALS = {
    "baldwin": 1_672_777,
    "hovde": 1_643_996,
    "total": 3_390_787,
}
OTHER_KEYS = [
    "kennedy",
    "stein",
    "oliver",
    "terry",
    "west",
    "deLaCruz",
    "sonski",
    "fox",
    "kienitz",
    "jenkins",
    "futureMadamPotus",
    "mcneil",
    "scattering",
]


def normalize_county(name: str) -> str:
    return name.replace(" County", "").replace("Fond Du Lac", "Fond du Lac")


def read_json(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def assert_equal(label: str, actual, expected, errors: list[str]) -> None:
    if actual != expected:
        errors.append(f"{label}: expected {expected!r}, got {actual!r}")


def main() -> int:
    errors: list[str] = []
    counties = read_json("president-county-results.json")
    labels = read_json("candidate-labels.json")
    ward_analysis = read_json("ward-analysis.json")
    geojson = read_json("wi-counties.geojson")
    turnout = read_json("turnout-data.json")

    assert_equal("county row count", len(counties), 72, errors)
    assert_equal("candidate label count", len(labels), len(OTHER_KEYS), errors)
    assert_equal("county geometry count", len(geojson["features"]), 72, errors)

    county_names = {row["county"] for row in counties}
    geometry_names = {normalize_county(feature["properties"]["NAME"]) for feature in geojson["features"]}
    assert_equal("county names match geometry names", sorted(county_names), sorted(geometry_names), errors)

    for row in counties:
      row_other = sum(row[key] for key in OTHER_KEYS)
      assert_equal(f"{row['county']} other breakdown", row_other, row["other"], errors)
      assert_equal(f"{row['county']} total", row["trump"] + row["harris"] + row["other"], row["total"], errors)
      assert_equal(f"{row['county']} margin", row["trump"] - row["harris"], row["margin"], errors)

    totals = {
        "trump": sum(row["trump"] for row in counties),
        "harris": sum(row["harris"] for row in counties),
        "other": sum(row["other"] for row in counties),
        "total": sum(row["total"] for row in counties),
    }
    for key, expected in EXPECTED_TOTALS.items():
        assert_equal(f"president statewide {key}", totals[key], expected, errors)

    ward_rows = ward_analysis["metadata"]["rows"]
    assert_equal("ward row count", len(ward_rows), ward_analysis["metadata"]["wardRows"], errors)
    assert_equal("ward row count expected", len(ward_rows), 3503, errors)
    ward_counties = {normalize_county(row["county"]) for row in ward_rows}
    assert_equal("ward counties covered", sorted(ward_counties), sorted(county_names), errors)

    ward_president = {
        "trump": sum(row["trump"] for row in ward_rows),
        "harris": sum(row["harris"] for row in ward_rows),
        "total": sum(row["total"] for row in ward_rows),
    }
    assert_equal("ward president Trump", ward_president["trump"], EXPECTED_TOTALS["trump"], errors)
    assert_equal("ward president Harris", ward_president["harris"], EXPECTED_TOTALS["harris"], errors)
    assert_equal("ward president total", ward_president["total"], EXPECTED_TOTALS["total"], errors)

    # Senate totals in ward-analysis include only the President/Senate rows used for graphs.
    # They are checked indirectly through known down-ballot values.
    baldwin = sum(round(row["harris"] * (1 - row["demDropoff"] / 100)) for row in ward_rows)
    hovde = sum(round(row["trump"] * (1 - row["repDropoff"] / 100)) for row in ward_rows)
    if abs(baldwin - EXPECTED_SENATE_TOTALS["baldwin"]) > 5:
        errors.append(f"reconstructed Baldwin total outside rounding tolerance: {baldwin}")
    if abs(hovde - EXPECTED_SENATE_TOTALS["hovde"]) > 5:
        errors.append(f"reconstructed Hovde total outside rounding tolerance: {hovde}")

    assert_equal("turnout metadata row count", len(turnout["rows"]), turnout["metadata"]["rows"], errors)
    for row in turnout["rows"]:
        if normalize_county(row["county"]) not in county_names:
            errors.append(f"turnout county not recognized: {row['county']}")
        if isinstance(row.get("turnoutPct"), (int, float)) and row["registeredVoters"] > 0:
            expected = round((row["ballotsCast"] / row["registeredVoters"]) * 100, 2)
            assert_equal(f"{row['county']} {row['ward']} turnoutPct", row["turnoutPct"], expected, errors)

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        json.dumps(
            {
                "status": "passed",
                "countyRows": len(counties),
                "wardRows": len(ward_rows),
                "countyFeatures": len(geojson["features"]),
                "turnoutRows": len(turnout["rows"]),
                "presidentTotals": totals,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
