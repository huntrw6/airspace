"""Refresh the bundled helicopter designators from ICAO Doc 8643."""

from __future__ import annotations

import argparse
import json
import re
import textwrap
import urllib.request
from pathlib import Path

SOURCE_URL = "https://doc8643.icao.int/External/AircraftTypes"
AIRCRAFT_FILE = Path(__file__).parents[1] / "airspace" / "aircraft.py"
BLOCK_PATTERN = re.compile(
    r"# BEGIN GENERATED ICAO HELICOPTER CODES\n.*?"
    r"# END GENERATED ICAO HELICOPTER CODES",
    re.DOTALL,
)


def fetch_helicopter_codes() -> list[str]:
    request = urllib.request.Request(SOURCE_URL, data=b"", method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        aircraft = json.load(response)
    return sorted(
        {
            item["Designator"].strip().upper()
            for item in aircraft
            if item.get("AircraftDescription") == "Helicopter"
            and item.get("Designator")
        }
    )


def render_block(codes: list[str]) -> str:
    wrapped = textwrap.fill(" ".join(codes), width=76, subsequent_indent="    ")
    return (
        "# BEGIN GENERATED ICAO HELICOPTER CODES\n"
        "ICAO_HELICOPTER_CODES = frozenset(\n"
        "    \"\"\"\n"
        f"    {wrapped}\n"
        "    \"\"\".split()\n"
        ")\n"
        "# END GENERATED ICAO HELICOPTER CODES"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit nonzero if the bundled list differs from the current ICAO data",
    )
    args = parser.parse_args()
    current = AIRCRAFT_FILE.read_text(encoding="utf-8")
    updated, replacements = BLOCK_PATTERN.subn(
        render_block(fetch_helicopter_codes()), current
    )
    if replacements != 1:
        raise RuntimeError("generated helicopter code block was not found exactly once")
    if updated == current:
        print("ICAO helicopter designators are current.")
        return 0
    if args.check:
        print("ICAO helicopter designators need to be refreshed.")
        return 1
    AIRCRAFT_FILE.write_text(updated, encoding="utf-8")
    print("Updated ICAO helicopter designators.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
