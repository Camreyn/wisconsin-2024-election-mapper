"""Validate and convert turnout CSV data into browser-ready JSON/JS files."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
VALID_TIMINGS = {"preElectionDay", "postElectionDay", "final", "unknown"}
REQUIRED = [
    "county",
    "municipality",
    "ward",
    "ballots_cast",
    "registered_voters",
    "registration_denominator_timing",
    "source_url",
]


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/import-turnout.py data/your-turnout-file.csv [data/another-turnout-file.csv ...]", file=sys.stderr)
        return 1
    sources = [Path(arg) for arg in sys.argv[1:]]
    missing_sources = [str(source) for source in sources if not source.exists()]
    if missing_sources:
        print(f"Missing turnout CSV: {', '.join(missing_sources)}", file=sys.stderr)
        return 1

    rows = []
    warnings = []
    source_names = []
    for source in sources:
        source_names.append(source.name)
        with source.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            missing = [field for field in REQUIRED if field not in (reader.fieldnames or [])]
            if missing:
                print(f"{source}: missing required columns: {', '.join(missing)}", file=sys.stderr)
                return 1

            for index, row in enumerate(reader, start=2):
                timing = row["registration_denominator_timing"].strip()
                if timing not in VALID_TIMINGS:
                    print(f"{source} line {index}: invalid timing {timing!r}", file=sys.stderr)
                    return 1
                try:
                    ballots_cast = int(row["ballots_cast"])
                    registered_voters = int(row["registered_voters"])
                except ValueError:
                    print(f"{source} line {index}: ballots_cast and registered_voters must be integers", file=sys.stderr)
                    return 1
                turnout_pct = None
                if registered_voters > 0:
                    turnout_pct = round((ballots_cast / registered_voters) * 100, 2)
                if timing in {"preElectionDay", "unknown"}:
                    warnings.append(f"{source.name}:{index}")
                rows.append(
                    {
                        "county": row["county"].strip(),
                        "municipality": row["municipality"].strip(),
                        "ward": row["ward"].strip(),
                        "ballotsCast": ballots_cast,
                        "registeredVoters": registered_voters,
                        "turnoutPct": turnout_pct,
                        "registrationDenominatorTiming": timing,
                        "sourceUrl": row["source_url"].strip(),
                        "sourceLevel": row.get("source_level", "ward").strip() or "ward",
                        "notes": row.get("notes", "").strip(),
                        "warningRequired": timing in {"preElectionDay", "unknown"},
                    }
                )

    payload = {
        "metadata": {
            "sourceCsv": ", ".join(source_names),
            "sourceCsvs": source_names,
            "rows": len(rows),
            "warningRows": len(warnings),
            "warningRule": "Warn when registration denominator timing is preElectionDay or unknown.",
        },
        "rows": rows,
    }
    (DATA / "turnout-data.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (DATA / "turnout-data.js").write_text(
        f"window.WI_TURNOUT_DATA = {json.dumps(payload, separators=(',', ':'))};\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["metadata"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
