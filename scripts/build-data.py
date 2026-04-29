"""Build browser data modules from source WEC files and JSON artifacts."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def read_json(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def write_js(name: str, global_name: str, value) -> None:
    payload = json.dumps(value, separators=(",", ":"))
    (DATA / name).write_text(f"window.{global_name} = {payload};\n", encoding="utf-8")


def main() -> None:
    president = read_json("president-county-results.json")
    labels = read_json("candidate-labels.json")
    ward_analysis = read_json("ward-analysis.json")
    counties = read_json("wi-counties.geojson")

    write_js(
        "app-data.js",
        "WI_ELECTION_APP_DATA",
        {
            "presidentCountyResults": president,
            "candidateLabels": labels,
        },
    )
    write_js("eta-data.js", "ETA_WARD_CHARTS", ward_analysis)
    write_js("wi-counties.js", "WI_COUNTIES_GEOJSON", counties)

    print(
        json.dumps(
            {
                "presidentCountyResults": len(president),
                "candidateLabels": len(labels),
                "wardRows": ward_analysis["metadata"]["wardRows"],
                "countyFeatures": len(counties["features"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
