from datetime import date

import pytest

from tradingagents.mcp.contracts import (
    BriefingRequest,
    ContractError,
    normalize_decision,
    validate_ticker,
    validate_trade_date,
)


def test_briefing_request_normalizes_safe_inputs():
    request = BriefingRequest.create("  btcusd  ", "2026-09-19", analyst="MARKET", asset_type="crypto")

    assert request.ticker == "btcusd"
    assert request.analyst == "market"
    assert request.asset_type == "crypto"


def test_trade_date_rejects_future_dates():
    with pytest.raises(ContractError, match="future"):
        validate_trade_date("2026-09-21", today=date(2026, 9, 20))


def test_ticker_rejects_path_traversal():
    with pytest.raises(ContractError):
        validate_ticker("../secrets")


def test_decision_requires_valid_rating_and_text():
    decision = normalize_decision({
        "rating": "Buy",
        "executive_summary": "Accumulate gradually.",
        "investment_thesis": "Earnings and trend support the call.",
        "price_target": "189.5",
    })

    assert decision["rating"] == "Buy"
    assert decision["price_target"] == 189.5

