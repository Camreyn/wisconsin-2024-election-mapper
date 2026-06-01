"""Validate generated historical Wisconsin presidential baseline artifacts."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT / "data" / "historical"
GENERATED = HISTORICAL / "generated"
VALID_SOURCE_CLASSES = {"nativeOfficial", "harmonizedLtsb"}
VALID_SOURCE_LEVELS = {"ward", "reportingUnit", "municipality", "county"}
VALID_ROW_METHODS = {"original", "ltsbPopulationAllocation", "unknown"}
EXPECTED_SERIES = {
    "ltsb-harmonized-2012-president": (7_008, 72),
    "ltsb-harmonized-2016-president": (7_008, 72),
    "ltsb-harmonized-2020-president": (7_008, 72),
    "wec-native-2016-president-original": (3_636, 72),
    "wec-native-2016-president-recount": (3_636, 72),
    "wec-native-2024-president": (3_503, 72),
}
REQUIRED_CSV_FIELDS = [
    "electionYear",
    "electionDate",
    "contestId",
    "contestName",
    "office",
    "party",
    "candidate",
    "county",
    "municipality",
    "reportingUnit",
    "ward",
    "votes",
    "sourceClass",
    "sourceLevel",
    "rowMethod",
    "sourceUrl",
    "sourceFile",
    "sourceSha256",
    "notes",
    "sourceId",
]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    errors = []
    manifest = read_json(HISTORICAL / "source-manifest.json")
    summary = read_json(GENERATED / "historical-presidential-summary.json")
    reconciliation = read_json(GENERATED / "historical-reconciliation-report.json")
    masked = read_json(GENERATED / "ltsb-masked-presidential-rows.json")

    for source in manifest["entries"]:
        if source.get("retrievalStatus") != "collected":
            continue
        local_file = HISTORICAL / source["localFile"]
        if not local_file.exists():
            errors.append(f"source file missing: {local_file}")
        elif sha256(local_file) != source.get("sha256"):
            errors.append(f"source hash mismatch: {source['id']}")

    if reconciliation.get("status") != "passed":
        errors.append("historical reconciliation report is not passing")
    for check in reconciliation.get("checks", []):
        if check.get("status") != "passed":
            errors.append(f"historical reconciliation check failed: {check.get('id')}")

    if masked["metadata"].get("rows") != 70 or len(masked.get("rows", [])) != 70:
        errors.append("expected exactly 70 preserved LTSB masked rows")

    series_by_id = {series["id"]: series for series in summary["series"]}
    if set(series_by_id) != set(EXPECTED_SERIES):
        errors.append(f"unexpected summary series: {sorted(series_by_id)}")

    for series_id, (expected_rows, expected_counties) in EXPECTED_SERIES.items():
        series = series_by_id.get(series_id)
        if not series:
            continue
        rows = series.get("rows", [])
        if series.get("rowCount") != expected_rows or len(rows) != expected_rows:
            errors.append(f"{series_id}: expected {expected_rows} rows, got {len(rows)}")
        counties = {row["county"] for row in rows}
        if len(counties) != expected_counties:
            errors.append(f"{series_id}: expected {expected_counties} counties, got {len(counties)}")
        sums = defaultdict(int)
        for row in rows:
            for field in ("county", "municipality", "reportingUnit", "ward", "sourceId"):
                if not str(row.get(field, "")).strip():
                    errors.append(f"{series_id}: required field missing: {field}")
            if row.get("sourceClass") not in VALID_SOURCE_CLASSES:
                errors.append(f"{series_id}: invalid source class: {row.get('sourceClass')}")
            if row.get("sourceLevel") not in VALID_SOURCE_LEVELS:
                errors.append(f"{series_id}: invalid source level: {row.get('sourceLevel')}")
            if row.get("rowMethod") not in VALID_ROW_METHODS:
                errors.append(f"{series_id}: invalid row method: {row.get('rowMethod')}")
            if row["dem"] + row["rep"] + row["other"] != row["total"]:
                errors.append(f"{series_id}: row total mismatch: {row['reportingUnit']}")
            for field in ("dem", "rep", "other", "total"):
                sums[field] += row[field]
        statewide = series["statewide"]
        for field in ("dem", "rep", "other", "total"):
            if sums[field] != statewide[field]:
                errors.append(f"{series_id}: statewide {field} mismatch")

    normalized_csv = GENERATED / "historical-presidential-results.csv.gz"
    seen = set()
    csv_rows = 0
    with gzip.open(normalized_csv, "rt", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing_fields = [field for field in REQUIRED_CSV_FIELDS if field not in (reader.fieldnames or [])]
        if missing_fields:
            errors.append(f"normalized CSV missing columns: {', '.join(missing_fields)}")
        for line_number, row in enumerate(reader, start=2):
            csv_rows += 1
            for field in REQUIRED_CSV_FIELDS:
                if not str(row.get(field, "")).strip():
                    errors.append(f"normalized CSV line {line_number}: missing {field}")
            if row.get("sourceClass") not in VALID_SOURCE_CLASSES:
                errors.append(f"normalized CSV line {line_number}: invalid sourceClass")
            if row.get("sourceLevel") not in VALID_SOURCE_LEVELS:
                errors.append(f"normalized CSV line {line_number}: invalid sourceLevel")
            if row.get("rowMethod") not in VALID_ROW_METHODS:
                errors.append(f"normalized CSV line {line_number}: invalid rowMethod")
            try:
                int(row["votes"])
            except ValueError:
                errors.append(f"normalized CSV line {line_number}: votes is not an integer")
            key = (
                row["contestId"],
                row.get("canvassStage", ""),
                row.get("geoid", ""),
                row["county"],
                row["municipality"],
                row["reportingUnit"],
                row["party"],
            )
            if key in seen:
                errors.append(f"normalized CSV line {line_number}: duplicate normalized key")
            seen.add(key)

    if csv_rows != summary["metadata"].get("normalizedCandidateRows") or csv_rows != 95_397:
        errors.append(f"expected 95397 normalized candidate rows, got {csv_rows}")

    if errors:
        print("Historical validation failed:")
        for error in errors[:100]:
            print(f"- {error}")
        if len(errors) > 100:
            print(f"- ... and {len(errors) - 100} more")
        return 1

    print(
        json.dumps(
            {
                "status": "passed",
                "manifestCollectedFiles": sum(1 for item in manifest["entries"] if item.get("retrievalStatus") == "collected"),
                "series": len(series_by_id),
                "normalizedCandidateRows": csv_rows,
                "maskedLtsbRows": len(masked["rows"]),
                "reconciliationChecks": len(reconciliation["checks"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
