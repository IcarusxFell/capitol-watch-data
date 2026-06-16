"""Feed freshness check (dead-man's-switch).

GitHub's built-in notifications tell you when the update *job fails*. This covers
the gap: the schedule silently stopped, or a run went green but the published
data is stale / suspiciously small. Run on its own daily schedule; a non-zero
exit makes GitHub email you.
"""
import datetime as dt
import json
import sys

MAX_AGE_HOURS = 36     # update runs daily; allow one missed/late run
MIN_HOUSE = 200
MIN_SENATE = 100
META_PATH = "data/metadata.json"


def evaluate(meta, now, max_age_hours=MAX_AGE_HOURS):
    """Pure function: returns a list of problem strings (empty == healthy)."""
    try:
        ts = dt.datetime.fromisoformat(meta["updated_utc"])
    except (KeyError, ValueError, TypeError):
        return ["metadata.json has no valid 'updated_utc'"]

    problems = []
    age = (now - ts).total_seconds() / 3600
    if age > max_age_hours:
        problems.append(f"feed is stale: last updated {age:.1f}h ago (> {max_age_hours}h)")

    counts = meta.get("counts", {})
    if counts.get("house", 0) < MIN_HOUSE:
        problems.append(f"house count too low: {counts.get('house', 0)} (< {MIN_HOUSE})")
    if counts.get("senate", 0) < MIN_SENATE:
        problems.append(f"senate count too low: {counts.get('senate', 0)} (< {MIN_SENATE})")
    return problems


def main():
    try:
        with open(META_PATH, encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"HEALTH CHECK FAILED: cannot read {META_PATH}: {exc}")
        sys.exit(1)

    problems = evaluate(meta, dt.datetime.now(dt.timezone.utc))
    print(f"metadata: {meta}")
    if problems:
        print("HEALTH CHECK FAILED:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("Feed healthy.")


if __name__ == "__main__":
    main()
