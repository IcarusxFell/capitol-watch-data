"""Data-quality gates.

These run before anything is published. If they fail, the GitHub Action exits
non-zero and the existing good data is left untouched — so a parser regression or
an upstream glitch can never overwrite a healthy feed with garbage.
"""

REQUIRED = ("transaction_date", "type", "amount", "asset_description")


def check(records, label, *, min_records, existing_count=0):
    """Return a list of problem strings (empty == healthy)."""
    problems = []
    n = len(records)

    if n < min_records:
        problems.append(f"{label}: only {n} records (expected >= {min_records})")

    if existing_count and n < existing_count * 0.5:
        problems.append(f"{label}: {n} records is <50% of the previous {existing_count} (possible regression)")

    missing = sum(1 for r in records if any(not r.get(k) for k in REQUIRED))
    if n and missing > n * 0.05:
        problems.append(f"{label}: {missing}/{n} records missing required fields (>5%)")

    no_date = sum(1 for r in records if not r.get("transaction_date"))
    if n and no_date > n * 0.05:
        problems.append(f"{label}: {no_date}/{n} records have no transaction date (>5%)")

    return problems
