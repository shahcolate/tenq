# tenq

**An AI equity analyst that actually reads the filings.**

One command turns a ticker into a cited research brief — grounded in SEC EDGAR
primary sources, with every claim traceable to the 10-K it came from.

```bash
pip install tenq
export ANTHROPIC_API_KEY=sk-...   # or OPENAI_API_KEY, or run Ollama locally
tenq AAPL -o aapl.md
```

## Why tenq

Most "AI investing" tools fall into two camps: trading simulators where LLM
personas debate stock picks, and thin wrappers around a quotes API. Both share
the same weakness — the model narrates from vibes, and you can't check its work.

tenq takes the opposite approach:

- **Primary sources only.** Fundamentals come from SEC XBRL company facts —
  the *exact values* companies filed, not a third-party aggregator. Risk
  factors and MD&A are extracted verbatim from the latest 10-K.
- **Numbers are never LLM-generated.** The financials table is rendered
  deterministically from filed data. The model writes narrative *around* the
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
| Net income | 97.0B | 93.7B | [1] |

## Sources
1. Apple Inc. Form 10-K (accession 0000320193-24-000123), XBRL company facts via SEC EDGAR — https://...
2. Apple Inc. Form 10-K, filed 2024-11-01 (accession 0000320193-24-000123) — https://...
```

## Bring your own LLM

| Provider | Setup | Default model |
|---|---|---|
| Anthropic (default) | `export ANTHROPIC_API_KEY=...` | `claude-opus-4-8` |
| OpenAI | `export OPENAI_API_KEY=...` | `gpt-4o-mini` |
| Ollama (fully local) | run `ollama serve` | `llama3.1` |

Override with `--provider` / `--model`, or `TENQ_PROVIDER` / `TENQ_MODEL`.

No key at all? `tenq AAPL --no-llm` still gives you the cited data dossier:
filed financials, verbatim risk factors, and MD&A extracts.

## Options

```
tenq TICKER [-o FILE] [--provider anthropic|openai|ollama] [--model NAME]
            [--no-llm] [--no-market]
```

- `--no-market` skips the indicative Yahoo Finance snapshot (needs
  `pip install tenq[market]`); everything else comes straight from the SEC.
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
        deterministic dossier (numbered sources)
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

- [ ] MCP server mode (`tenq serve`) — use it from Claude, Cursor, or any MCP client
- [ ] 10-Q support for quarterly deltas
- [ ] Peer comparison (`tenq AAPL --vs MSFT,GOOGL`)
- [ ] PDF export

## Development

```bash
pip install -e ".[dev]"
pytest
```

The test suite runs fully offline against recorded SEC API shapes.

## License

MIT
