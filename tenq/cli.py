"""tenq CLI: `tenq AAPL` -> a cited research brief in Markdown."""

from __future__ import annotations

import argparse
import sys

from . import __version__, brief, dossier, llm
from .edgar import EdgarClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tenq",
        description="An AI equity analyst that actually reads the filings.",
    )
    parser.add_argument("ticker", help="US-listed ticker, e.g. AAPL")
    parser.add_argument("-o", "--out", help="Write the brief to this file instead of stdout")
    parser.add_argument("--provider", choices=["anthropic", "openai", "ollama"],
                        help="LLM provider (default: auto-detect from environment)")
    parser.add_argument("--model", help="Model override for the chosen provider")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip the LLM narrative; output the cited data dossier only")
    parser.add_argument("--no-market", action="store_true",
                        help="Skip the Yahoo Finance market snapshot")
    parser.add_argument("--version", action="version", version=f"tenq {__version__}")
    args = parser.parse_args(argv)

    def status(msg: str) -> None:
        print(msg, file=sys.stderr)

    try:
        status(f"tenq: resolving {args.ticker.upper()} on SEC EDGAR ...")
        d = dossier.build(args.ticker, EdgarClient(), include_market=not args.no_market)
        status(f"tenq: {d.company} (CIK {d.cik}) — "
               f"{len(d.metrics)} metric series, "
               f"10-K {'found' if d.filing else 'not found'}")
    except LookupError as exc:
        print(f"tenq: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # network / SEC errors
        print(f"tenq: failed to fetch EDGAR data: {exc}", file=sys.stderr)
        return 1

    narrative = None
    if not args.no_llm:
        try:
            provider = llm.resolve_provider(args.provider)
            status(f"tenq: writing narrative with {provider} ...")
            narrative = llm.complete(brief.build_prompt(d), provider=provider, model=args.model)
        except llm.LLMError as exc:
            print(f"tenq: {exc}", file=sys.stderr)
            print("tenq: falling back to data-only dossier (--no-llm).", file=sys.stderr)

    output = brief.compose_brief(d, narrative)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(output)
        status(f"tenq: wrote {args.out}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
