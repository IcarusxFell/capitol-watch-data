"""House of Representatives PTR scraper.

Pipeline:
  1. Download the yearly bulk index ZIP (clean tab-separated list of filings).
  2. Keep FilingType == 'P' (Periodic Transaction Report).
  3. Digital filings (DocID starts with '20') -> extract text with pypdf.
     Scanned filings -> optional OCR (skipped if tesseract not installed).
  4. Parse transactions and emit the app's House schema.
"""
import csv
import io
import re
import zipfile

from pypdf import PdfReader

from . import normalize as N
from .http_util import get

BASE = "https://disclosures-clerk.house.gov"
INDEX_URL = BASE + "/public_disc/financial-pdfs/{year}FD.zip"
PDF_URL = BASE + "/public_disc/ptr-pdfs/{year}/{doc}.pdf"

# A transaction line: type letter (+ optional partial/full), two dates, amount range.
_TX = re.compile(
    r"\b([PSE])\b\s*(\((?:partial|full)\))?\s+"
    r"(\d{2}/\d{2}/\d{4})\s*(\d{2}/\d{2}/\d{4})\s*"
    r"\$\s*([\d,]+)\s*-\s*\$\s*([\d,]+)",
    re.IGNORECASE,
)
_TICKER = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,5})\)")
_OWNER_LEAD = re.compile(r"^(SP|JT|DC)\b", re.IGNORECASE)
_ASSET_CODE = re.compile(r"\[[A-Z]{2}\]")          # [ST] [GS] [OT] ...
_FOOTNOTE = re.compile(r"^[A-Z]\s+[A-Z].*:.*$")     # "F S: New", "S O: ..." artifacts
_SHARES = re.compile(r"[A-Za-z.]{1,6}\s*[–\-]\s*[\d,.]+\s*shares?.*?/share", re.IGNORECASE)
_FULLTX = re.compile(r"the full transaction included.*", re.IGNORECASE)


def filings_from_index(year):
    """Yield dicts for each PTR in the year's bulk index."""
    raw = get(_OPENER, INDEX_URL.format(year=year))
    zf = zipfile.ZipFile(io.BytesIO(raw))
    name = next(n for n in zf.namelist() if n.endswith(".txt"))
    text = zf.read(name).decode("latin-1")
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        if row.get("FilingType") != "P":
            continue
        yield {
            "doc": row["DocID"].strip(),
            "year": row["Year"].strip() or str(year),
            "name": f"{row['First']} {row['Last']}".strip(),
            "district": row["StateDst"].strip(),
            "filing_date": row["FilingDate"].strip(),
            "digital": row["DocID"].strip().startswith("20"),
        }


def _segment_asset(segment):
    """From the text before a transaction match, pull owner, ticker, asset name."""
    lines = [ln.strip() for ln in segment.splitlines() if ln.strip()]
    lines = [ln for ln in lines if not _FOOTNOTE.match(ln)]
    block = " ".join(lines[-2:]) if lines else ""
    owner = ""
    om = _OWNER_LEAD.match(block)            # owner code only if it leads the block
    if om:
        owner = om.group(1)
        block = block[om.end():]
    tickers = _TICKER.findall(block)
    ticker = tickers[-1] if tickers else None
    asset = block[: block.rfind("(")] if ticker and "(" in block else block
    asset = _SHARES.sub("", asset)          # drop bundled "X – n shares @ $/share" comment text
    asset = _FULLTX.sub("", asset)
    asset = _ASSET_CODE.sub("", asset)
    asset = _TICKER.sub("", asset)
    asset = N.clean_text(asset, fallback="Undisclosed asset")
    return owner, ticker, asset


def parse_text(text, meta):
    """Parse one filing's extracted text into transaction records."""
    out, seen = [], set()
    prev_end = 0
    for m in _TX.finditer(text):
        owner, ticker, asset = _segment_asset(text[prev_end:m.start()])
        prev_end = m.end()
        rec = {
            "disclosure_date": m.group(4) or meta["filing_date"],
            "transaction_date": m.group(3),
            "owner": N.owner_word(owner),
            "ticker": N.clean_ticker(ticker),
            "asset_description": asset,
            "type": N.type_word(m.group(1), m.group(2)),
            "amount": N.clean_amount(f"${m.group(5)} - ${m.group(6)}"),
            "representative": N.clean_text(meta["name"], "Unknown Member"),
            "district": meta["district"] or None,
            "source_url": PDF_URL.format(year=meta["year"], doc=meta["doc"]),
        }
        key = (rec["transaction_date"], rec["ticker"], rec["asset_description"], rec["amount"], rec["type"])
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


def _ocr_text(pdf_bytes):
    try:
        import pdf2image
        import pytesseract
    except ImportError:
        return ""
    pages = pdf2image.convert_from_bytes(pdf_bytes, dpi=200)
    return "\n".join(pytesseract.image_to_string(p) for p in pages)


def extract_text(pdf_bytes, digital):
    text = ""
    try:
        text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf_bytes)).pages)
    except Exception:  # noqa: BLE001
        text = ""
    if len(text) < 300 and not digital:
        text = _ocr_text(pdf_bytes) or text
    return text


_OPENER = None


def scrape(years, opener, limit=None, log=print):
    """Scrape the given years; returns (records, stats)."""
    global _OPENER
    _OPENER = opener
    records, scanned_skipped, parsed_filings = [], 0, 0
    for year in years:
        filings = list(filings_from_index(year))
        if limit:
            filings = filings[:limit]
        log(f"[house] {year}: {len(filings)} PTRs")
        for f in filings:
            try:
                pdf = get(opener, PDF_URL.format(year=f["year"], doc=f["doc"]))
            except Exception as exc:  # noqa: BLE001
                log(f"[house]   download failed {f['doc']}: {exc}")
                continue
            text = extract_text(pdf, f["digital"])
            if len(text) < 300 and not f["digital"]:
                scanned_skipped += 1
                continue
            recs = parse_text(text, f)
            if recs:
                parsed_filings += 1
            records.extend(recs)
    stats = {"records": len(records), "parsed_filings": parsed_filings, "scanned_skipped": scanned_skipped}
    return records, stats
