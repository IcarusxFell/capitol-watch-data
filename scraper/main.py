"""Orchestrator: scrape House + Senate, validate, and publish JSON.

  python -m scraper.main                 # full run, writes data/*.json
  python -m scraper.main --limit 5       # quick smoke test (5 filings each)
  python -m scraper.main --chamber house # one chamber only
"""
import argparse
import datetime as dt
import json
import os

from . import house, quality, senate
from .http_util import make_opener

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
HOUSE_FILE = "house_transactions.json"
SENATE_FILE = "senate_transactions.json"
META_FILE = "metadata.json"


def _load_count(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return len(json.load(fh))
    except (OSError, ValueError):
        return 0


def _write(path, records):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def run(chamber, years, since, limit):
    os.makedirs(DATA_DIR, exist_ok=True)
    opener = make_opener()
    problems, written = [], {}

    if chamber in ("house", "all"):
        recs, stats = house.scrape(years, opener, limit=limit)
        print(f"[house] {stats}")
        existing = _load_count(os.path.join(DATA_DIR, HOUSE_FILE))
        probs = quality.check(recs, "house", min_records=1 if limit else 200, existing_count=existing)
        problems += probs
        if not probs:
            _write(os.path.join(DATA_DIR, HOUSE_FILE), recs)
            written["house"] = len(recs)

    if chamber in ("senate", "all"):
        recs, stats = senate.scrape(since, opener, limit=limit)
        print(f"[senate] {stats}")
        existing = _load_count(os.path.join(DATA_DIR, SENATE_FILE))
        probs = quality.check(recs, "senate", min_records=1 if limit else 100, existing_count=existing)
        problems += probs
        if not probs:
            _write(os.path.join(DATA_DIR, SENATE_FILE), recs)
            written["senate"] = len(recs)

    if written:
        meta = {"updated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "counts": written}
        _write(os.path.join(DATA_DIR, META_FILE), meta)

    if problems:
        print("\nQUALITY GATES FAILED — existing data left untouched:")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)
    print(f"\nOK. Published: {written}")


def main():
    this_year = dt.date.today().year
    ap = argparse.ArgumentParser()
    ap.add_argument("--chamber", choices=["house", "senate", "all"], default="all")
    ap.add_argument("--years", type=int, nargs="+", default=[this_year, this_year - 1])
    ap.add_argument("--since", default=f"01/01/{this_year - 1}", help="Senate: MM/DD/YYYY")
    ap.add_argument("--limit", type=int, default=None, help="cap filings per chamber (smoke test)")
    args = ap.parse_args()
    run(args.chamber, args.years, args.since, args.limit)


if __name__ == "__main__":
    main()
