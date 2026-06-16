"""Senate PTR scraper.

Pipeline:
  1. Load the eFD home page, grab the CSRF token, accept the usage agreement.
  2. Query the server-side DataTables JSON API for Periodic Transaction Reports.
  3. For each *electronic* report, fetch the HTML and parse its transaction table.
     (Paper filings are PDFs; they're a small minority and skipped for now.)
"""
import json
import re
import urllib.parse
from html.parser import HTMLParser

from . import normalize as N
from .http_util import get

BASE = "https://efdsearch.senate.gov"
HOME = BASE + "/search/home/"
DATA = BASE + "/search/report/data/"
REPORT_TYPE_PTR = "[11]"


class _TableParser(HTMLParser):
    """Collects rows of <td> cell text from the first data table on the page."""

    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell, self._in = [], None, None, False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag == "td" and self._row is not None:
            self._cell, self._in = [], True

    def handle_data(self, data):
        if self._in:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self._row is not None:
            self._row.append("".join(self._cell).strip())
            self._in = False
        elif tag == "tr" and self._row:
            self.rows.append(self._row)
            self._row = None


def _csrf(opener):
    html = get(opener, HOME).decode("utf-8", "ignore")
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    if not token:
        raise RuntimeError("Senate CSRF token not found")
    return token.group(1)


def _accept(opener, csrf):
    body = urllib.parse.urlencode({"prohibition_agreement": "1", "csrfmiddlewaretoken": csrf}).encode()
    get(opener, HOME, data=body, headers={"Referer": HOME})


def _search(opener, csrf, start, length, since):
    body = urllib.parse.urlencode({
        "csrfmiddlewaretoken": csrf,
        "start": str(start), "length": str(length),
        "report_types": REPORT_TYPE_PTR, "filer_types": "[]",
        "submitted_start_date": f"{since} 00:00:00", "submitted_end_date": "",
        "candidate_state": "", "senator_state": "", "office_id": "",
        "first_name": "", "last_name": "",
    }).encode()
    raw = get(opener, DATA, data=body, headers={
        "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrf, "Referer": BASE + "/search/",
    })
    return json.loads(raw.decode("utf-8", "ignore"))


def _parse_report(opener, href, senator, filed):
    html = get(opener, BASE + href).decode("utf-8", "ignore")
    parser = _TableParser()
    parser.feed(html)
    out = []
    for cells in parser.rows:
        # columns: #, Transaction Date, Owner, Ticker, Asset Name, Asset Type, Type, Amount, Comment
        if len(cells) < 8 or not re.match(r"\d{2}/\d{2}/\d{4}", cells[1]):
            continue
        out.append({
            "transaction_date": cells[1],
            "owner": N.clean_text(cells[2], "Self"),
            "ticker": N.clean_ticker(cells[3]),
            "asset_description": N.clean_text(cells[4], "Undisclosed asset"),
            "asset_type": N.clean_text(cells[5], "") or None,
            "type": N.clean_text(cells[6], "Other"),
            "amount": N.clean_amount(cells[7]),
            "comment": N.clean_text(cells[8], "") if len(cells) > 8 else "",
            "senator": senator,
            "ptr_link": BASE + href,
            "disclosure_date": filed,
        })
    return out


def scrape(since, opener, limit=None, log=print):
    csrf = _csrf(opener)
    _accept(opener, csrf)
    first = _search(opener, csrf, 0, 1, since)
    total = int(first.get("recordsTotal", 0))
    log(f"[senate] {total} PTRs since {since}")

    links = []
    start, page = 0, 100
    while start < total:
        data = _search(opener, csrf, start, page, since)
        for row in data.get("data", []):
            joined = " ".join(str(c) for c in row)
            href = re.search(r'href="(/search/view/ptr/[^"]+)"', joined)
            if not href:
                continue  # paper filing or non-electronic
            senator = re.sub(r"\s*\((Senator|Senate Candidate|Former Senator)\)\s*$", "",
                             re.sub(r"<[^>]+>", "", str(row[2])).strip())
            filed = next((str(c) for c in reversed(row) if re.match(r"\d{2}/\d{2}/\d{4}", str(c))), "")
            links.append((href.group(1), senator, filed))
        start += page
    if limit:
        links = links[:limit]

    records, parsed = [], 0
    for href, senator, filed in links:
        try:
            recs = _parse_report(opener, href, senator, filed)
        except Exception as exc:  # noqa: BLE001
            log(f"[senate]   report failed {href}: {exc}")
            continue
        if recs:
            parsed += 1
        records.extend(recs)
    return records, {"records": len(records), "parsed_reports": parsed, "electronic_links": len(links)}
