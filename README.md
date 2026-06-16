# capitol-watch-data

Your **own, independent** data feed for the Capitol Watch app. A scheduled
scraper pulls congressional STOCK Act disclosures straight from the official
House and Senate sources, parses them, and publishes JSON — no third-party
mirror in the loop.

## How it works

```
House Clerk bulk ZIP  ─┐
                       ├─►  scraper/  ──►  data/house_transactions.json
Senate eFD search API ─┘                  data/senate_transactions.json
                                          data/metadata.json
        (daily GitHub Action)
```

- **House** (`scraper/house.py`): downloads the yearly bulk index ZIP, keeps the
  Periodic Transaction Reports (PTRs), and extracts text from the digital PDFs
  (~88%). Scanned PDFs (~12%, detectable by DocID before download) are routed to
  OCR (Tesseract) when available.
- **Senate** (`scraper/senate.py`): completes the eFD CSRF/agreement flow, queries
  the report-search JSON API, and parses each electronic report's HTML table.
- **Output** matches the exact JSON schema the app already reads, so switching the
  app to this feed is a one-line URL change.

Measured against live data at build time: **~770 House PTRs/yr + ~250 Senate
PTRs/yr** — tiny volume, which is why this runs comfortably on free infrastructure.

## Output schema

House records: `disclosure_date, transaction_date, owner, ticker,
asset_description, type, amount, representative, district, source_url`

Senate records: `transaction_date, owner, ticker, asset_description, asset_type,
type, amount, comment, senator, ptr_link, disclosure_date`

Dates are `MM/DD/YYYY`; `owner` is `Self / Spouse / Joint / Dependent Child`;
`type` is `Purchase / Sale / Sale (Partial) / Exchange`.

## Run it locally

```bash
pip install -r requirements.txt          # pypdf (+ optional OCR libs)
python -m scraper.main --limit 5         # quick smoke test
python -m scraper.main                    # full run -> data/*.json
python -m unittest discover -s tests -v   # unit tests
```

OCR for scanned House filings also needs system packages:
`tesseract-ocr` and `poppler-utils` (the CI installs these automatically).

## Deploy (free, ~10 min)

1. Create a **public** GitHub repo named `capitol-watch-data` and push this folder.
2. **Settings → Actions → General:** allow workflows to run.
3. The workflow (`.github/workflows/update-data.yml`) runs **daily** and on manual
   trigger ("Run workflow"). Run it once to populate `data/`.
4. In the app, edit `CapitolWatch/Networking/TradeService.swift` and replace
   `YOUR_GITHUB_USERNAME` in `houseURLs` / `senateURLs`. (The app already falls
   back to the community mirror until your feed is live.)

## Security hardening (recommended — see the in-app review)

- ✅ **Turn on 2FA** for your GitHub account (the single most important step).
- ✅ **Branch protection** on `main`: require pull-request review so no one — not
  even a collaborator — can push unreviewed changes.
- ✅ **Minimal Action permissions** — the workflow only requests `contents: write`.
- ✅ **Pin Actions to a commit SHA** (replace `@v4`/`@v5` with the SHA). Dependabot
  (`.github/dependabot.yml`) is configured to keep both Actions and pip deps current.
- ✅ **Quality gates** (`scraper/quality.py`) fail the build instead of publishing
  bad data, so a parser regression or upstream glitch can't overwrite good data.
- ✅ **Stdlib-only networking** (no `requests`/`bs4`) keeps the dependency surface
  small — just `pypdf` (+ optional OCR).

## Monitoring (so you're alerted to failures)

Two layers, both free:

1. **Update job failure → GitHub emails you.** Enable it once at
   **github.com → Settings → Notifications → Actions → "Send notifications for
   failed workflows only."** Covers parser breaks (the quality gates fail the run).
2. **Feed goes stale → health check emails you.** `.github/workflows/health-check.yml`
   runs daily and fails if `data/metadata.json` is older than 36h or the counts
   look too small — catching the cases a failed-job email can't (the schedule
   silently stopping, or a green run that didn't actually refresh the data).
   Logic is in `scraper/healthcheck.py` (unit-tested).

## Maintenance reality (honest)

The recurring work is keeping the **House PDF parser** happy as filing layouts
drift — that's where occasional fixes are needed (a real example is handled in
`_segment_asset`). The quality gates will fail loudly when this happens rather
than ship garbage. Volume is low and the Senate side is structured HTML, so
upkeep is periodic, not constant.

> Data is sourced from public STOCK Act filings. For information only — not
> investment advice; may be incomplete or delayed.
