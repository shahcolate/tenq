from tenq import brief, dossier
from tenq.cli import main


def _build(client):
    return dossier.build("AAPL", client, include_market=False)


def test_dossier_build(client):
    d = _build(client)
    assert d.company == "Apple Inc."
    assert d.filing.accession == "0000320193-24-000123"
    assert d.risk_factors and d.mdna
    # every contributing filing has a numbered source
    assert d.accession_refs
    assert len(d.sources) >= 2


def test_financials_table_cites_sources(client):
    d = _build(client)
    table = brief.render_financials_table(d)
    assert "FY2023" in table and "FY2024" in table
    assert "391.0B" in table  # exact filed revenue, formatted
    assert "[1]" in table or "[2]" in table  # citation markers present


def test_financials_table_derived_rows(client):
    d = _build(client)
    table = brief.render_financials_table(d)
    # margins and growth computed from filed values, marked as derived
    assert "| Operating margin | 29.8% | 31.5% | derived |" in table
    assert "| Net margin | 25.3% | 24.0% | derived |" in table
    # FY2023 growth needs FY2022 revenue, which the fixtures don't have
    assert "| Revenue growth (YoY) | — | 2.0% | derived |" in table
    assert "never by the LLM" in table


def test_prompt_contains_rules_and_data(client):
    d = _build(client)
    prompt = brief.build_prompt(d)
    assert "Cite sources inline" in prompt
    assert "No price targets" in prompt
    assert "391.0B" in prompt
    assert "Risk Factors" in prompt


def test_compose_brief_no_llm(client):
    d = _build(client)
    out = brief.compose_brief(d, narrative=None)
    assert "Apple Inc. (AAPL)" in out
    assert "## Sources" in out
    assert "investment advice" in out  # disclaimer present


def test_cli_no_llm(client, capsys, monkeypatch):
    # client fixture already patched the HTTP boundary on EdgarClient
    rc = main(["AAPL", "--no-llm", "--no-market"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "research brief" in out
    assert "## Sources" in out


def test_cli_unknown_ticker(client, capsys):
    rc = main(["ZZZZZZ", "--no-llm", "--no-market"])
    assert rc == 1
    assert "not found" in capsys.readouterr().err
