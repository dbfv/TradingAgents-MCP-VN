from datetime import date

import pytest

from tradingagents.mcp import services
from tradingagents.mcp.contracts import ContractError


def test_health_does_not_require_llm_credentials(monkeypatch):
    monkeypatch.setattr(
        services,
        "_get_config",
        lambda: {"data_vendors": {"core_stock_apis": "yfinance", "macro_data": "fred"}},
    )
    monkeypatch.delenv("FRED_API_KEY", raising=False)

    result = services.health()

    assert result["llm_required"] is False
    assert result["status"] == "degraded"
    assert result["data_credentials_present"]["FRED_API_KEY"] is False


def test_briefing_returns_source_labelled_data_without_llm(monkeypatch):
    monkeypatch.setattr(services, "_vendor_for", lambda method: "fixture")
    monkeypatch.setattr(services, "_canonical_symbol", lambda ticker: ticker.upper())
    monkeypatch.setattr(services, "_route", lambda method, *args, **kwargs: f"fixture:{method}:{args[0]}")
    monkeypatch.setattr(services, "_fetch_verified_snapshot", lambda *args: {
        "name": "verified_market_snapshot",
        "method": "get_verified_market_snapshot",
        "vendor": "fixture",
        "status": "ok",
        "data": "fixture:snapshot",
    })

    result = services.get_analysis_briefing("NVDA", "2026-09-19", analyst="market")

    assert result["llm_required"] is False
    assert result["instrument"]["canonical_ticker"] == "NVDA"
    assert {item["status"] for item in result["sources"]} == {"ok"}


def test_portfolio_rejects_non_object_and_renders_position():
    with pytest.raises(ContractError, match="JSON object"):
        services.validate_portfolio("not-json", ticker="NVDA")

    result = services.validate_portfolio(
        {
            "cash": 1000,
            "currency": "USD",
            "positions": [{"ticker": "NVDA", "quantity": 2, "average_price": 100}],
        },
        ticker="NVDA",
    )

    assert result["valid"] is True
    assert "2 units" in result["rendered"]


def test_decision_validation_rejects_missing_thesis(monkeypatch):
    with pytest.raises(ContractError, match="investment_thesis"):
        services.validate_and_record_decision(
            "NVDA",
            "2026-09-19",
            {"rating": "Hold", "executive_summary": "Wait"},
        )

