"""Assemble a cited data dossier for a ticker from primary sources."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import market
from .edgar import EdgarClient, FilingRef, MetricSeries

# Keep prompts bounded; both sections are long in real filings.
MAX_SECTION_CHARS = 18_000


@dataclass
class Source:
    """A numbered, citable source."""

    ref: int
    description: str
    url: str


@dataclass
class Dossier:
    ticker: str
    company: str
    cik: int
    metrics: list[MetricSeries] = field(default_factory=list)
    filing: FilingRef | None = None
    risk_factors: str | None = None
    mdna: str | None = None
    market: dict | None = None
    sources: list[Source] = field(default_factory=list)
    # accession number -> source ref, so table rows can cite their filing
    accession_refs: dict[str, int] = field(default_factory=dict)


def build(ticker: str, client: EdgarClient | None = None, include_market: bool = True) -> Dossier:
    client = client or EdgarClient()
    cik, company = client.ticker_to_cik(ticker)
    dossier = Dossier(ticker=ticker.upper(), company=company, cik=cik)

    dossier.metrics = client.company_facts(cik)
    _register_fact_sources(dossier)

    filing = client.latest_filing(cik, "10-K")
    if filing:
        dossier.filing = filing
        ref = _add_source(
            dossier,
            f"{company} Form {filing.form}, filed {filing.filing_date} "
            f"(accession {filing.accession})",
            filing.url,
        )
        dossier.accession_refs.setdefault(filing.accession, ref)
        sections = client.filing_sections(filing)
        dossier.risk_factors = _clip(sections.get("risk_factors"))
        dossier.mdna = _clip(sections.get("mdna"))

    if include_market:
        dossier.market = market.snapshot(ticker)
        if dossier.market:
            _add_source(
                dossier,
                f"Market data snapshot via Yahoo Finance (indicative, not a primary source)",
                f"https://finance.yahoo.com/quote/{ticker.upper()}",
            )

    return dossier


def _register_fact_sources(dossier: Dossier) -> None:
    """Give every distinct filing that contributed an XBRL fact a source number."""
    for series in dossier.metrics:
        for p in series.points:
            if p.accn not in dossier.accession_refs:
                url = (
                    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
                    f"&CIK={dossier.cik:010d}&type=10-K&dateb=&owner=include&count=10"
                )
                ref = _add_source(
                    dossier,
                    f"{dossier.company} Form {p.form} (accession {p.accn}), "
                    f"XBRL company facts via SEC EDGAR",
                    url,
                )
                dossier.accession_refs[p.accn] = ref


def _add_source(dossier: Dossier, description: str, url: str) -> int:
    ref = len(dossier.sources) + 1
    dossier.sources.append(Source(ref=ref, description=description, url=url))
    return ref


def _clip(text: str | None) -> str | None:
    if text and len(text) > MAX_SECTION_CHARS:
        return text[:MAX_SECTION_CHARS] + "\n[... truncated ...]"
    return text
