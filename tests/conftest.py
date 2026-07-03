import json

import pytest

from tenq.edgar import FACTS_URL, SUBMISSIONS_URL, TICKERS_URL, EdgarClient

TICKERS = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp"},
}

def _flow(fy, start, end, val, accn, form="10-K", fp="FY", filed="2024-11-01"):
    return {"fy": fy, "fp": fp, "form": form, "start": start, "end": end,
            "val": val, "accn": accn, "filed": filed}

COMPANY_FACTS = {
    "cik": 320193,
    "facts": {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        # quarterly entry — must be excluded (short duration)
                        _flow(2024, "2024-07-01", "2024-09-28", 94_930_000_000, "0000320193-24-000123", form="10-Q", fp="Q4"),
                        # annual entries
                        _flow(2023, "2022-09-25", "2023-09-30", 383_285_000_000, "0000320193-23-000106", filed="2023-11-03"),
                        _flow(2024, "2023-10-01", "2024-09-28", 391_035_000_000, "0000320193-24-000123", filed="2024-11-01"),
                        # duplicate FY2023 restated in the FY2024 filing (later filed wins)
                        _flow(2023, "2022-09-25", "2023-09-30", 383_285_000_000, "0000320193-24-000123", filed="2024-11-01"),
                    ]
                }
            },
            "OperatingIncomeLoss": {
                "units": {
                    "USD": [
                        _flow(2023, "2022-09-25", "2023-09-30", 114_301_000_000, "0000320193-23-000106", filed="2023-11-03"),
                        _flow(2024, "2023-10-01", "2024-09-28", 123_216_000_000, "0000320193-24-000123", filed="2024-11-01"),
                    ]
                }
            },
            "NetIncomeLoss": {
                "units": {
                    "USD": [
                        _flow(2023, "2022-09-25", "2023-09-30", 96_995_000_000, "0000320193-23-000106", filed="2023-11-03"),
                        _flow(2024, "2023-10-01", "2024-09-28", 93_736_000_000, "0000320193-24-000123", filed="2024-11-01"),
                    ]
                }
            },
            "Assets": {
                "units": {
                    "USD": [
                        {"fy": 2024, "fp": "FY", "form": "10-K", "end": "2024-09-28",
                         "val": 364_980_000_000, "accn": "0000320193-24-000123", "filed": "2024-11-01"},
                    ]
                }
            },
        }
    },
}

SUBMISSIONS = {
    "cik": "0000320193",
    "filings": {
        "recent": {
            "form": ["8-K", "10-K", "10-Q"],
            "accessionNumber": ["0000320193-24-000999", "0000320193-24-000123", "0000320193-24-000077"],
            "primaryDocument": ["a8k.htm", "aapl-20240928.htm", "a10q.htm"],
            "filingDate": ["2024-11-20", "2024-11-01", "2024-08-02"],
            "reportDate": ["2024-11-20", "2024-09-28", "2024-06-29"],
        }
    },
}

# Fixture stand-ins for the verbatim 10-K sections (not the actual filing text).
RISK_BODY = (
    "The Company's business, results of operations and financial condition are "
    "subject to a number of risks and uncertainties. Our business depends on "
    "global supply chains, and substantially all of the Company's manufacturing "
    "is performed in whole or in part by outsourcing partners located primarily "
    "in Asia. A significant concentration of this manufacturing is performed by "
    "a small number of partners, often in single locations. Disruptions at these "
    "partners — whether from public health issues, geopolitical tension, trade "
    "restrictions or natural disasters — could materially delay product "
    "shipments and increase costs. The Company also faces intense competition "
    "in all of its markets from rivals that aggressively cut prices and offer "
    "lower-margin alternatives; the Company's ability to compete depends on its "
    "continued introduction of innovative new products, which is inherently "
    "uncertain. In addition, the Company is exposed to foreign-exchange "
    "fluctuations across the many currencies in which it sells, to changing "
    "trade policies and tariffs between the United States and its trading "
    "partners, and to evolving regulatory scrutiny of its digital-services "
    "businesses in the United States and Europe, any of which could adversely "
    "affect gross margins and the ways in which the Company currently operates "
    "its App Store and services offerings. The Company's success also depends "
    "on the continued service and availability of highly skilled employees, on "
    "the security of its information technology systems against increasingly "
    "sophisticated attacks, and on protecting the confidential information of "
    "its customers; an actual or perceived failure on any of these fronts could "
    "result in legal exposure, remediation costs and lasting reputational harm."
)
MDNA_BODY = (
    "Net sales increased during fiscal 2024 driven by services. Total net sales "
    "rose 2% compared to 2023, as growth in Services — including advertising, "
    "cloud offerings and payment services — more than offset a modest decline "
    "in Products revenue. Products gross margin was consistent with the prior "
    "year, while Services gross margin expanded on a favorable mix shift, "
    "lifting total company gross margin. Operating expenses grew more slowly "
    "than revenue as the Company balanced continued investment in research and "
    "development against disciplined general and administrative spending; R&D "
    "growth reflected higher headcount devoted to silicon engineering and "
    "machine-learning initiatives. The Company generated strong operating cash "
    "flow during the year and returned capital to shareholders through "
    "dividends and share repurchases under its authorized programs. Looking "
    "ahead, management expects foreign-exchange headwinds to remain a factor in "
    "reported revenue and notes that the timing of new product introductions "
    "can shift net sales between quarters. The Company believes its balances "
    "of cash, cash equivalents and marketable securities, together with cash "
    "generated by ongoing operations and continued access to debt markets, "
    "will be sufficient to satisfy its cash requirements and capital return "
    "program over the next twelve months. Critical accounting estimates, "
    "including those relating to revenue recognition and income taxes, were "
    "unchanged during the year and are discussed in the notes to the "
    "consolidated financial statements. The Company's effective tax rate for "
    "the year reflected the impact of a one-time charge related to a state "
    "aid decision, partially offset by a lower statutory rate on foreign "
    "earnings and the benefit of research and development tax credits."
)

FAKE_10K_HTML = f"""
<html><head><style>.x{{color:red}}</style><script>var x=1;</script></head><body>
<p>TABLE OF CONTENTS</p>
<p>Item 1A. Risk Factors ....... 5</p>
<p>Item 7. Management's Discussion and Analysis ....... 20</p>
<p>Item 1. Business</p>
<p>The Company designs, manufactures and markets smartphones.</p>
<p>Item 1A. Risk Factors</p>
<p>{RISK_BODY}</p>
<p>Item 1B. Unresolved Staff Comments</p>
<p>None.</p>
<p>Item 7. Management's Discussion and Analysis of Financial Condition</p>
<p>{MDNA_BODY}</p>
<p>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</p>
</body></html>
"""


@pytest.fixture
def client(monkeypatch):
    """EdgarClient with the HTTP boundary stubbed to serve fixtures."""
    c = EdgarClient(user_agent="tenq-tests test@example.com")

    def fake_get_json(self, url):
        if url == TICKERS_URL:
            return json.loads(json.dumps(TICKERS))
        if url == FACTS_URL.format(cik=320193):
            return json.loads(json.dumps(COMPANY_FACTS))
        if url == SUBMISSIONS_URL.format(cik=320193):
            return json.loads(json.dumps(SUBMISSIONS))
        raise AssertionError(f"unexpected URL {url}")

    def fake_get_text(self, url):
        assert "aapl-20240928.htm" in url
        return FAKE_10K_HTML

    monkeypatch.setattr(EdgarClient, "_get_json", fake_get_json)
    monkeypatch.setattr(EdgarClient, "_get_text", fake_get_text)
    return c
