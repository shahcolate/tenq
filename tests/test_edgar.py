import pytest

from tenq.edgar import RISK_FACTORS_END, RISK_FACTORS_START, extract_section, html_to_text


def test_ticker_to_cik(client):
    cik, title = client.ticker_to_cik("aapl")
    assert cik == 320193
    assert title == "Apple Inc."


def test_ticker_not_found(client):
    with pytest.raises(LookupError):
        client.ticker_to_cik("ZZZZZZ")


def test_company_facts_annual_only(client):
    series = client.company_facts(320193)
    by_label = {s.label: s for s in series}

    revenue = by_label["Revenue"]
    assert [p.fy for p in revenue.points] == [2023, 2024]
    # the quarterly 10-Q entry must not leak in
    assert all(p.form == "10-K" for p in revenue.points)
    # restated FY2023 from the later filing wins
    assert revenue.points[0].accn == "0000320193-24-000123"

    assert by_label["Total assets"].points[0].val == 364_980_000_000


def test_latest_filing(client):
    filing = client.latest_filing(320193, "10-K")
    assert filing.accession == "0000320193-24-000123"
    assert filing.filing_date == "2024-11-01"
    assert "aapl-20240928.htm" in filing.url
    assert "000032019324000123" in filing.url  # accession without dashes


def test_filing_sections(client):
    filing = client.latest_filing(320193, "10-K")
    sections = client.filing_sections(filing)
    assert "supply chains" in sections["risk_factors"]
    assert "Net sales increased" in sections["mdna"]
    # TOC line must not be selected as the section body
    assert "......." not in sections["risk_factors"]
    assert "......." not in sections["mdna"]
    # the heading remainder must not leak into the extract
    assert not sections["mdna"].lower().startswith("and analysis")


def test_html_to_text_strips_script_and_style():
    text = html_to_text("<style>.a{}</style><script>bad()</script><p>Hello</p><p>World</p>")
    assert "bad()" not in text and ".a{}" not in text
    assert "Hello" in text and "World" in text


def test_extract_section_prefers_body_over_toc():
    text = (
        "Item 1A. Risk Factors 5\n"  # TOC
        "Item 1B. Comments 6\n"
        "Item 1A. Risk Factors\n" + ("Real risk content here. " * 200) +
        "\nItem 1B. Unresolved Staff Comments"
    )
    section = extract_section(text, RISK_FACTORS_START, RISK_FACTORS_END)
    assert section.startswith("Real risk content") or "Real risk content" in section
    assert len(section) > 1500
