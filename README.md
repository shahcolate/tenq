# tenq

[![CI](https://github.com/shahcolate/tenq/actions/workflows/ci.yml/badge.svg)](https://github.com/shahcolate/tenq/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://github.com/shahcolate/tenq/blob/main/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/shahcolate/tenq/blob/main/LICENSE)

**An AI equity analyst that actually reads the filings.**

One command turns a ticker into a cited research brief — grounded in SEC EDGAR
primary sources, with every claim traceable to the 10-K it came from.

```bash
pip install git+https://github.com/shahcolate/tenq.git
export ANTHROPIC_API_KEY=sk-...   # or OPENAI_API_KEY, or run Ollama locally
tenq AAPL -o aapl.md
```

No API key at all? `tenq AAPL --no-llm` still gives you the cited data dossier:
filed financials with derived margins, verbatim risk factors, and MD&A extracts.
[See a full sample output →](examples/AAPL-data-only-sample.md)

## Why tenq

Most "AI investing" tools fall into two camps: trading simulators where LLM
personas debate stock picks, and thin wrappers around a quotes API. Both share
the same weakness — the model narrates from vibes, and you can't check its work.

|  | tenq | LLM stock-picker bots | quote-API wrappers |
|---|---|---|---|
| Data source | SEC EDGAR filings (primary) | model memory + vibes | third-party aggregators |
| Financial figures | exact filed XBRL values | LLM-generated | aggregator-normalized |
| Citations | every paragraph, down to the accession number | none | rare |
| Ratings & price targets | none, by design | buy/sell theater | varies |
| Works fully local | yes (Ollama) | usually not | usually not |

The design rules behind that column:

- **Primary sources only.** Fundamentals come from SEC XBRL company facts —
  the *exact values* companies filed, not a third-party aggregator. Risk
  factors and MD&A are extracted verbatim from the latest 10-K.
- **Numbers are never LLM-generated.** The financials table is rendered
  deterministically from filed data — including derived rows (margins, YoY
  growth) computed by tenq itself. The model writes narrative *around* the
  data, not the data itself.
- **Every paragraph is cited.** The narrative must reference the numbered
  source list — each source is a specific filing with its accession number and
  a link back to EDGAR. If the filings don't support a claim, tenq is
  instructed to say so instead of guessing.
- **No ratings, no price targets.** tenq automates the boring part of research
  (reading the filings), not the judgment.

## What you get

```markdown
# Apple Inc. (AAPL) — research brief

## Business snapshot
Apple designs, manufactures and markets smartphones ... [2]

## Financial trajectory
Revenue grew from $383.3B in FY2023 to $391.0B in FY2024 [1], while net
income declined to $93.7B ... [1]

## Key risks (from the 10-K)
Management flags dependence on global supply chains ... [2]

...

## Appendix: filed financials
| Metric (USD unless noted) | FY2023 | FY2024 | Source |
|---|---|---|---|
| Revenue | 383.3B | 391.0B | [1] |
| Operating income | 114.3B | 123.2B | [1][2] |
| Net income | 97.0B | 93.7B | [1][2] |
| Revenue growth (YoY) | — | 2.0% | derived |
| Operating margin | 29.8% | 31.5% | derived |
| Net margin | 25.3% | 24.0% | derived |

## Sources
1. Apple Inc. Form 10-K (accession 0000320193-24-000123), XBRL company facts via SEC EDGAR — https://...
2. Apple Inc. Form 10-K, filed 2024-11-01 (accession 0000320193-24-000123) — https://...
```

Rows marked "derived" are computed by tenq from the filed values above —
never by the LLM.

## Bring your own LLM

| Provider | Setup | Default model |
|---|---|---|
| Anthropic (default) | `export ANTHROPIC_API_KEY=...` | `claude-opus-4-8` |
| OpenAI | `export OPENAI_API_KEY=...` | `gpt-4o-mini` |
| Ollama (fully local) | run `ollama serve` | `llama3.1` |

Override with `--provider` / `--model`, or `TENQ_PROVIDER` / `TENQ_MODEL`.

## Options

```
tenq TICKER [-o FILE] [--provider anthropic|openai|ollama] [--model NAME]
            [--no-llm] [--no-market] [--version]
```

- `--no-llm` skips the narrative and outputs the cited data dossier only.
- `--no-market` skips the indicative Yahoo Finance snapshot (needs the
  `market` extra: `pip install "tenq[market] @ git+https://github.com/shahcolate/tenq.git"`);
  everything else comes straight from the SEC.
- Set `TENQ_USER_AGENT="your-app your-email@example.com"` — the SEC's fair
  access policy asks all API users to identify themselves.

## How it works

```
ticker ─► SEC company_tickers.json ─► CIK
        ─► XBRL companyfacts  ──► 5y annual series (exact filed values + accession numbers)
        ─► submissions API    ──► latest 10-K ─► Item 1A + Item 7 text (verbatim)
        ─► [optional] Yahoo Finance snapshot
                 │
                 ▼
        deterministic dossier (numbered sources, derived margins & growth)
                 │
                 ▼
        your LLM writes the narrative — citations required, no invented numbers
```

## Limitations (honest ones)

- US filers only — it's built on SEC EDGAR.
- The LLM narrative can still misread the data it's given; the citations exist
  so *you* can check it in seconds.
- Section extraction from 10-K HTML is heuristic; unusual filing layouts may
  yield partial Risk Factors / MD&A text.
- Not investment advice. Nothing here rates, ranks, or predicts.

## Roadmap

- [ ] PyPI release (`pip install tenq`)
- [ ] MCP server mode (`tenq serve`) — use it from Claude, Cursor, or any MCP client
- [ ] 10-Q support for quarterly deltas
- [ ] Peer comparison (`tenq AAPL --vs MSFT,GOOGL`)
- [ ] PDF export

Want one of these sooner? [Open or upvote an issue](https://github.com/shahcolate/tenq/issues).

## Contributing

```bash
git clone https://github.com/shahcolate/tenq && cd tenq
pip install -e ".[dev]"
pytest
```

The test suite runs fully offline against recorded SEC API shapes, and CI
covers Python 3.9–3.12. Bug reports with a ticker that misbehaves are
especially welcome — EDGAR filings are wonderfully inconsistent.

If tenq saved you a read through a 300-page 10-K, a ⭐ helps other people
find it.

## License

MIT
