"""SEC EDGAR client: CIK lookup, XBRL company facts, and 10-K section extraction.

Every datapoint returned carries the accession number, form type, and filing
date it came from, so downstream output can cite the primary source exactly.

SEC fair-access policy requires a User-Agent identifying the caller:
https://www.sec.gov/os/accessing-edgar-data
Set TENQ_USER_AGENT to "your-app-name your-email@example.com".
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

import requests

from . import __version__

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FILING_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{doc}"

# (label, XBRL tag candidates in preference order, unit key, "flow" or "instant")
METRICS = [
    ("Revenue", ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"], "USD", "flow"),
    ("Operating income", ["OperatingIncomeLoss"], "USD", "flow"),
    ("Net income", ["NetIncomeLoss"], "USD", "flow"),
    ("Diluted EPS", ["EarningsPerShareDiluted"], "USD/shares", "flow"),
    ("Operating cash flow", ["NetCashProvidedByUsedInOperatingActivities"], "USD", "flow"),
    ("Total assets", ["Assets"], "USD", "instant"),
    ("Stockholders' equity", ["StockholdersEquity"], "USD", "instant"),
    ("Cash & equivalents", ["CashAndCashEquivalentsAtCarryingValue"], "USD", "instant"),
]

# A fiscal-year "flow" fact must span at least this many days (rejects quarterly facts).
MIN_ANNUAL_DURATION_DAYS = 300
SECTION_MIN_CHARS = 1500


@dataclass
class DataPoint:
    fy: int
    end: str
    val: float
    accn: str
    form: str
    filed: str


@dataclass
class MetricSeries:
    label: str
    tag: str
    unit: str
    points: list[DataPoint] = field(default_factory=list)


@dataclass
class FilingRef:
    form: str
    accession: str
    filing_date: str
    report_date: str
    url: str


class _TextExtractor(HTMLParser):
    """Strip an HTML filing down to visible text."""

    _SKIP = {"script", "style"}
    _BLOCK = {"p", "div", "tr", "table", "br", "li", "h1", "h2", "h3", "h4"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        elif tag in self._BLOCK:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self._chunks.append(data)

    def text(self) -> str:
        raw = "".join(self._chunks)
        raw = raw.replace("\xa0", " ")
        raw = re.sub(r"[ \t]+", " ", raw)
        return re.sub(r"\n\s*\n+", "\n", raw).strip()


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text()


def extract_section(text: str, start_pattern: str, end_patterns: list[str]) -> str | None:
    """Extract a filing section (e.g. Item 1A) from flattened filing text.

    A 10-K mentions each item heading in the table of contents and again in
    the body. The body heading comes later, so we take the LAST occurrence
    whose span is substantial; a TOC match either has a tiny span (next TOC
    line) or engulfs the body heading, and loses either way.
    """
    starts = list(re.finditer(start_pattern, text, re.IGNORECASE))
    if not starts:
        return None
    ends = []
    for pat in end_patterns:
        ends.extend(m.start() for m in re.finditer(pat, text, re.IGNORECASE))
    ends.sort()

    candidates = []
    for m in starts:
        stop = next((e for e in ends if e > m.end()), len(text))
        candidates.append(text[m.end():stop].strip())
    for candidate in reversed(candidates):
        if len(candidate) >= SECTION_MIN_CHARS:
            return candidate
    return max(candidates, key=len) or None


RISK_FACTORS_START = r"item\s+1a[\.\:\s–—-]{0,4}\s*risk\s+factors"
RISK_FACTORS_END = [r"item\s+1b[\.\:\s]", r"item\s+2[\.\:\s]"]
MDNA_START = r"item\s+7[\.\:\s–—-]{0,4}\s*management['’]?s\s+discussion"
MDNA_END = [r"item\s+7a[\.\:\s]", r"item\s+8[\.\:\s]"]


class EdgarClient:
    def __init__(self, user_agent: str | None = None, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        ua = user_agent or os.environ.get("TENQ_USER_AGENT") or (
            f"tenq/{__version__} (+https://github.com/shahcolate/tenq)"
        )
        self.session.headers["User-Agent"] = ua

    def _get_json(self, url: str) -> dict:
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _get_text(self, url: str) -> str:
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.text

    def ticker_to_cik(self, ticker: str) -> tuple[int, str]:
        """Resolve a ticker to (CIK, company title)."""
        data = self._get_json(TICKERS_URL)
        want = ticker.upper().strip()
        for entry in data.values():
            if entry["ticker"].upper() == want:
                return int(entry["cik_str"]), entry["title"]
        raise LookupError(
            f"Ticker {ticker!r} not found in SEC company list (US filers only)."
        )

    def company_facts(self, cik: int) -> list[MetricSeries]:
        """Pull annual (10-K, full fiscal year) series for the core metrics."""
        data = self._get_json(FACTS_URL.format(cik=cik))
        gaap = data.get("facts", {}).get("us-gaap", {})
        series: list[MetricSeries] = []
        for label, tags, unit, kind in METRICS:
            for tag in tags:
                fact = gaap.get(tag)
                if not fact or unit not in fact.get("units", {}):
                    continue
                points = self._annual_points(fact["units"][unit], kind)
                if points:
                    series.append(MetricSeries(label=label, tag=tag, unit=unit, points=points))
                    break
        return series

    @staticmethod
    def _annual_points(entries: list[dict], kind: str) -> list[DataPoint]:
        by_fy: dict[int, DataPoint] = {}
        for e in entries:
            if e.get("form") != "10-K" or e.get("fp") != "FY" or e.get("fy") is None:
                continue
            if kind == "flow":
                start, end = e.get("start"), e.get("end")
                if not start or not end:
                    continue
                if _days_between(start, end) < MIN_ANNUAL_DURATION_DAYS:
                    continue
            point = DataPoint(
                fy=int(e["fy"]), end=e["end"], val=e["val"],
                accn=e["accn"], form=e["form"], filed=e.get("filed", ""),
            )
            prior = by_fy.get(point.fy)
            # Amended/later filings win.
            if prior is None or point.filed >= prior.filed:
                by_fy[point.fy] = point
        return [by_fy[fy] for fy in sorted(by_fy)][-5:]

    def latest_filing(self, cik: int, form: str = "10-K") -> FilingRef | None:
        data = self._get_json(SUBMISSIONS_URL.format(cik=cik))
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        for i, f in enumerate(forms):
            if f == form:
                accession = recent["accessionNumber"][i]
                doc = recent["primaryDocument"][i]
                url = FILING_INDEX_URL.format(
                    cik=cik, accession_nodash=accession.replace("-", ""), doc=doc
                )
                return FilingRef(
                    form=form,
                    accession=accession,
                    filing_date=recent["filingDate"][i],
                    report_date=recent.get("reportDate", [""] * len(forms))[i],
                    url=url,
                )
        return None

    def filing_sections(self, filing: FilingRef) -> dict[str, str]:
        """Fetch the primary document and pull out Risk Factors and MD&A."""
        text = html_to_text(self._get_text(filing.url))
        sections = {}
        risk = extract_section(text, RISK_FACTORS_START, RISK_FACTORS_END)
        if risk:
            sections["risk_factors"] = risk
        mdna = extract_section(text, MDNA_START, MDNA_END)
        if mdna:
            sections["mdna"] = mdna
        return sections


def _days_between(start: str, end: str) -> int:
    from datetime import date

    y1, m1, d1 = (int(x) for x in start.split("-"))
    y2, m2, d2 = (int(x) for x in end.split("-"))
    return (date(y2, m2, d2) - date(y1, m1, d1)).days
