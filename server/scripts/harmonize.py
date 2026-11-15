"""Fit the harmonization parameters and run the validation report.

Usage (from ``server/``, with the API stopped for ``fit``)::

    python scripts/harmonize.py fit                       # writes table harmonization_params
    python scripts/harmonize.py report                    # fit period from HARMONIZE_* settings
    python scripts/harmonize.py report --start 2013-01-01 --end 2013-12-31 --out reports/2013

``fit`` computes the VIIRS/MODIS day, night and total ratios, the Terra factor
and the minimum reliable monthly count (reliability test 3), and stores them
with their fit periods and detection counts, so the API never recomputes them.

``report`` writes ``report.md``, ``report.json`` and ``proportionality.svg``
(default folder ``reports/harmonization``) with the ratios, the seasonal check,
leave-one-month-out cross-validation (national and 1° boxes; MAPE, WAPE, r²)
and the 4 reliability tests. It only reads the database.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent.parent
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import duckdb  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from harmonizer.config import BOX_SIZE_DEG, load_config  # noqa: E402
from harmonizer.data import monthly_counts  # noqa: E402
from harmonizer.params import fit_params, save_params  # noqa: E402
from harmonizer.validation import (  # noqa: E402
    build_report,
    check_proportionality,
    scatter_svg,
    to_markdown,
)


def _date(text: str) -> date:
    """argparse type for ``YYYY-MM-DD``."""
    return date.fromisoformat(text)


def cmd_fit(db: Path) -> int:
    """Fit and store the parameters.

    Args:
        db: DuckDB file (opened for writing).

    Returns:
        Exit code.
    """
    config = load_config()
    with duckdb.connect(str(db)) as connection:
        boxes = monthly_counts(connection, config.fit_start, config.fit_end, by_box=True, box_size=BOX_SIZE_DEG)
        reliable = check_proportionality(boxes)["min_reliable_count"] if boxes else None
        params = fit_params(connection, config, reliable)
        save_params(connection, params)
    print(json.dumps(params.as_dict(), indent=2))
    print(f"Stored in table harmonization_params of {db}")
    return 0


def cmd_report(db: Path, start: date | None, end: date | None, reference_year: int, out: Path) -> int:
    """Build the validation report and write it to ``out``.

    Args:
        db: DuckDB file (read-only).
        start: First day of the analyzed overlap period (None = fit start).
        end: Last day (None = fit end).
        reference_year: Reference year of test 1.
        out: Output folder.

    Returns:
        Exit code.
    """
    config = load_config()
    out.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(db), read_only=True) as connection:
        report = build_report(connection, config, start, end, reference_year,
                              progress=lambda msg: print(msg, flush=True))
    t3 = report["test3_proportionality"]
    points = t3.pop("points")
    (out / "proportionality.svg").write_text(
        scatter_svg(points, report["ratios"]["total"], "MODIS vs VIIRS (Suomi-NPP) per 1° box-month"),
        encoding="utf-8",
    )
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "report.md").write_text(to_markdown(report, "proportionality.svg"), encoding="utf-8")
    print(f"Report written to {out}/report.md")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point.

    Args:
        argv: Arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Exit code.
    """
    load_dotenv(SERVER_DIR / ".env", override=False)
    parser = argparse.ArgumentParser(description="MODIS/VIIRS harmonization: fit and validate.")
    parser.add_argument("--db", type=Path, default=SERVER_DIR / "data/hotspots.duckdb")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("fit", help="Fit ratios, Terra factor and reliable count; store them in the database")
    rep = sub.add_parser("report", help="Write the validation report (read-only)")
    rep.add_argument("--start", type=_date, help="First day of the overlap period analyzed")
    rep.add_argument("--end", type=_date, help="Last day of the overlap period analyzed")
    rep.add_argument("--reference-year", type=int, default=2013)
    rep.add_argument("--out", type=Path, default=SERVER_DIR / "reports/harmonization")
    args = parser.parse_args(argv)
    if args.command == "fit":
        return cmd_fit(args.db)
    return cmd_report(args.db, args.start, args.end, args.reference_year, args.out)


if __name__ == "__main__":
    sys.exit(main())
