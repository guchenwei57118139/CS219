#!/usr/bin/env python3
"""
Aggregate status_code counts from Open5GS NRF test result files.

Usage:
  python aggregate_status_codes.py [results_dir]
  If results_dir is omitted, uses the directory containing this script.

Input:
  - Directory containing JSON files named: nrf_test_results_open5gs_{operation}.json
  - Each file has structure: {"results": [{"status_code": <int|null>, ...}, ...], ...}
  - "operation" is the part between "nrf_test_results_open5gs_" and ".json".

Output:
  - A single JSON file in the same directory as the input files.
  - Default output filename: status_code_summary.json
  - Format: {"{operation}": {"{status_code}": <count>, ...}, ...}
  - status_code is serialized as string (e.g. "200", "400", "null" for missing).

Example:
  If nrf_test_results_open5gs_NFRegister.json has 50 results with status_code 400
  and 10 with status_code 201, one entry will be:
  "NFRegister": {"400": 50, "201": 10}
"""

import json
import re
import sys
from pathlib import Path


def main():
    script_dir = Path(__file__).resolve().parent
    results_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else script_dir

    pattern = re.compile(r"^nrf_test_results_open5gs_NF(.+)\.json$")
    summary = {}

    for path in sorted(results_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".json":
            continue
        m = pattern.match(path.name)
        if not m:
            continue
        operation = m.group(1)

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: skip {path.name}: {e}", file=sys.stderr)
            continue

        results = data.get("results")
        if not isinstance(results, list):
            print(f"Warning: no 'results' array in {path.name}", file=sys.stderr)
            summary[operation] = {}
            continue

        counts = {}
        for item in results:
            sc = item.get("status_code")
            key = str(sc) if sc is not None else "Crashed"
            counts[key] = counts.get(key, 0) + 1

        summary[operation] = dict(sorted(counts.items(), key=lambda x: (x[0] == "null", x[0])))

    out_path = results_dir / "status_code_summary.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"Summary written to {out_path}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
