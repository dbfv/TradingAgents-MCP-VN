"""Deterministic services exposed to Claude Code through MCP.

The functions in this module are deliberately model-agnostic.  Vendor
adapters are imported only when a briefing is requested, so a health check can
run without LangChain, LangGraph, or provider credentials.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .contracts import (
    BriefingRequest,
    ContractError,
    jsonable,
    normalize_decision,
    parse_json_object,
    validate_ticker,
    validate_trade_date,
)


def _get_config() -> dict[str, Any]:
    from tradingagents.dataflows.config import get_config

    return get_config()


def _canonical_symbol(ticker: str) -> str:
    try:
        from tradingagents.dataflows.symbol_utils import normalize_symbol

        return normalize_symbol(ticker)
    except Exception:
        # A vendor dependency should not make the contract layer unusable.
        return ticker.strip().upper()


def _vendor_for(method: str) -> str:
    try:
        from tradingagents.dataflows.interface import get_category_for_method, get_vendor

        return get_vendor(get_category_for_method(method), method)
    except Exception:
        return "configured vendor"


def _route(method: str, *args: Any, **kwargs: Any) -> Any:
    from tradingagents.dataflows.interface import route_to_vendor

    return route_to_vendor(method, *args, **kwargs)


def _source_status(value: Any) -> str:
    text = str(value or "")
    if text.startswith(("DATA_UNAVAILABLE:", "NO_DATA_AVAILABLE:")):
        return "unavailable"
    return "ok"


def _bounded_text(value: Any, max_chars: int = 24_000) -> str:
    text = str(value if value is not None else "")
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[TRUNCATED_BY_MCP: request a narrower window]"


def _fetch(label: str, method: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    vendor = _vendor_for(method)
    try:
        value = _route(method, *args, **kwargs)
        value = _bounded_text(value)
        status = _source_status(value)
        return {"name": label, "method": method, "vendor": vendor, "status": status, "data": value}
    except Exception as exc:  # vendor boundaries must be visible, not fatal to the briefing
        return {
            "name": label,
            "method": method,
            "vendor": vendor,
            "status": "unavailable",
            "data": f"DATA_UNAVAILABLE: {type(exc).__name__}: {exc}",
        }


def _fetch_verified_snapshot(ticker: str, trade_date: str, look_back_days: int) -> dict[str, Any]:
    try:
        from tradingagents.dataflows.market_data_validator import build_verified_market_snapshot

        value = build_verified_market_snapshot(ticker, trade_date, look_back_days)
        return {
            "name": "verified_market_snapshot",
            "method": "get_verified_market_snapshot",
            "vendor": "configured market data",
            "status": _source_status(value),
            "data": _bounded_text(value),
        }
    except Exception as exc:
        return {
            "name": "verified_market_snapshot",
            "method": "get_verified_market_snapshot",
            "vendor": "configured market data",
            "status": "unavailable",
            "data": f"DATA_UNAVAILABLE: {type(exc).__name__}: {exc}",
        }


def _window_start(trade_date: str, look_back_days: int) -> str:
    parsed = datetime.strptime(trade_date, "%Y-%m-%d").date()
    return (parsed - timedelta(days=look_back_days)).isoformat()


def _profile_calls(request: BriefingRequest) -> list[tuple[str, Callable[[], dict[str, Any]]]]:
    ticker = _canonical_symbol(request.ticker)
    start = _window_start(request.trade_date, request.look_back_days)
    d = request.trade_date
    n = request.look_back_days

    market = [
        ("price_history", lambda: _fetch("price_history", "get_stock_data", ticker, start, d)),
        ("technical_rsi", lambda: _fetch("technical_rsi", "get_indicators", ticker, "rsi", d, n)),
        ("technical_macd", lambda: _fetch("technical_macd", "get_indicators", ticker, "macd", d, n)),
        ("verified_market_snapshot", lambda: _fetch_verified_snapshot(ticker, d, n)),
    ]
    fundamentals = [
        ("fundamentals", lambda: _fetch("fundamentals", "get_fundamentals", ticker, d)),
        ("balance_sheet", lambda: _fetch("balance_sheet", "get_balance_sheet", ticker, "quarterly", d)),
        ("cashflow", lambda: _fetch("cashflow", "get_cashflow", ticker, "quarterly", d)),
        ("income_statement", lambda: _fetch("income_statement", "get_income_statement", ticker, "quarterly", d)),
    ]
    news = [
        ("ticker_news", lambda: _fetch("ticker_news", "get_news", ticker, start, d)),
        ("global_news", lambda: _fetch("global_news", "get_global_news", d, min(n, 30), None)),
        ("insider_transactions", lambda: _fetch("insider_transactions", "get_insider_transactions", ticker, d)),
        ("macro_fed_funds", lambda: _fetch("macro_fed_funds", "get_macro_indicators", "fed_funds_rate", d, min(n, 365))),
        ("prediction_markets", lambda: _fetch("prediction_markets", "get_prediction_markets", ticker, 6, d)),
    ]
    social = [
        ("social_news_proxy", lambda: _fetch("social_news_proxy", "get_news", ticker, start, d)),
    ]
    profiles = {
        "market": market,
        "technical": market,
        "fundamentals": fundamentals,
        "news": news,
        "social": social,
    }
    if request.analyst == "all":
        return market + fundamentals + news + social
    return profiles[request.analyst]


def get_analysis_briefing(
    ticker: str,
    trade_date: str,
    analyst: str = "market",
    asset_type: str = "stock",
    look_back_days: int = 30,
) -> dict[str, Any]:
    """Collect one bounded, source-labelled analyst briefing.

    This function never calls an LLM.  It returns source text plus explicit
    unavailable markers so Claude Code can distinguish missing data from a
    negative market signal.
    """
    request = BriefingRequest.create(ticker, trade_date, analyst, asset_type, look_back_days)
    canonical = _canonical_symbol(request.ticker)
    sources: list[dict[str, Any]] = []
    for _, call in _profile_calls(request):
        sources.append(jsonable(call()))
    warnings = [
        f"{item['name']} unavailable"
        for item in sources
        if item.get("status") == "unavailable"
    ]
    instrument_label = "asset" if request.asset_type == "crypto" else "instrument"
    return {
        "instrument": {
            "input_ticker": request.ticker,
            "canonical_ticker": canonical,
            "asset_type": request.asset_type,
            "context": (
                f"The {instrument_label} to analyze is `{request.ticker}`. "
                "Keep this exact ticker in every report and recommendation."
            ),
        },
        "trade_date": request.trade_date,
        "analyst": request.analyst,
        "look_back_days": request.look_back_days,
        "llm_required": False,
        "sources": sources,
        "warnings": warnings,
    }


def health() -> dict[str, Any]:
    """Return MCP/data readiness without inspecting or requiring LLM keys."""
    config = _get_config()
    vendors = config.get("data_vendors", {})
    key_by_vendor = {
        "alpha_vantage": "ALPHA_VANTAGE_API_KEY",
        "fred": "FRED_API_KEY",
    }
    credentials = {
        env_name: bool(os.getenv(env_name))
        for vendor, env_name in key_by_vendor.items()
        if vendor in str(vendors).lower()
    }
    warnings = [
        f"{vendor} is selected but {env_name} is not configured"
        for vendor, env_name in key_by_vendor.items()
        if vendor in str(vendors).lower() and not credentials.get(env_name)
    ]
    return {
        "status": "ok" if not warnings else "degraded",
        "server": "tradingagents-mcp",
        "llm_required": False,
        "data_vendors": jsonable(vendors),
        "data_credentials_present": credentials,
        "warnings": warnings,
    }


def validate_portfolio(portfolio: Any = None, ticker: str = "") -> dict[str, Any]:
    """Validate a portfolio object without accepting filesystem paths."""
    ticker = validate_ticker(ticker) if ticker else ""
    if portfolio is None:
        return {
            "provided": False,
            "valid": True,
            "rendered": (
                "Portfolio context: not provided. Do not assume the caller has "
                "a flat book; provide sizing guidance they can apply."
            ),
            "portfolio": None,
        }
    value = parse_json_object(portfolio, field_name="portfolio")
    positions = value.get("positions", [])
    if not isinstance(positions, list):
        raise ContractError("portfolio.positions must be a list")
    normalized_positions = []
    for position in positions:
        if not isinstance(position, dict) or not position.get("ticker"):
            raise ContractError("each portfolio position needs a ticker")
        position_ticker = validate_ticker(str(position["ticker"]))
        try:
            quantity = float(position["quantity"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractError("each portfolio position needs numeric quantity") from exc
        average_price = position.get("average_price")
        if average_price is not None:
            try:
                average_price = float(average_price)
            except (TypeError, ValueError) as exc:
                raise ContractError("average_price must be numeric or null") from exc
        normalized_positions.append({
            "ticker": position_ticker,
            "quantity": quantity,
            "average_price": average_price,
        })
    cash = value.get("cash")
    if cash is not None:
        try:
            cash = float(cash)
        except (TypeError, ValueError) as exc:
            raise ContractError("portfolio.cash must be numeric or null") from exc
    normalized = {
        "cash": cash,
        "currency": str(value["currency"]) if value.get("currency") is not None else None,
        "positions": normalized_positions,
    }
    held = next((p for p in normalized_positions if p["ticker"].upper() == ticker.upper()), None)
    lines = [
        f"- Current position in {ticker.upper()}: {held['quantity']:,.4g} units"
        if held
        else f"- No current position in {ticker.upper()}"
    ]
    if held and held["average_price"] is not None:
        lines[0] += f", average price {held['average_price']:,.2f}"
    if cash is not None:
        currency = f" {normalized['currency']}" if normalized["currency"] else ""
        lines.append(f"- Cash available: {cash:,.2f}{currency}")
    return {"provided": True, "valid": True, "portfolio": normalized, "rendered": "Portfolio at the analysis date:\n" + "\n".join(lines)}


def get_prior_lessons(ticker: str, as_of: str | None = None) -> dict[str, Any]:
    """Read prior resolved lessons with point-in-time filtering."""
    ticker = validate_ticker(ticker)
    if as_of is not None:
        as_of = validate_trade_date(as_of)
    from tradingagents.agents.utils.memory import TradingMemoryLog

    log = TradingMemoryLog(_get_config())
    return {
        "ticker": ticker,
        "as_of": as_of,
        "lessons": log.get_past_context(ticker, as_of=as_of),
        "entries": jsonable(log.load_entries()),
    }


def _render_decision(decision: dict[str, Any]) -> str:
    parts = [
        f"**Rating**: {decision['rating']}",
        "",
        f"**Executive Summary**: {decision['executive_summary']}",
        "",
        f"**Investment Thesis**: {decision['investment_thesis']}",
        "",
        f"**Price Target**: {decision['price_target'] if decision['price_target'] is not None else 'not provided'}",
        "",
        f"**Time Horizon**: {decision['time_horizon'] or 'not provided'}",
    ]
    return "\n".join(parts)


def validate_and_record_decision(
    ticker: str,
    trade_date: str,
    decision: Any,
    reports: Any = None,
    reflection: str | None = None,
) -> dict[str, Any]:
    """Validate Claude's decision and persist it using existing formats."""
    ticker = validate_ticker(ticker)
    trade_date = validate_trade_date(trade_date)
    normalized = normalize_decision(decision)
    report_map = parse_json_object(reports or {}, field_name="reports")
    final_decision = _render_decision(normalized)

    from tradingagents.agents.utils.memory import TradingMemoryLog
    from tradingagents.reporting import write_report_tree

    config = _get_config()
    memory = TradingMemoryLog(config)
    memory.store_decision(ticker, trade_date, final_decision)

    report_state = dict(report_map)
    report_state["final_trade_decision"] = final_decision
    report_state["risk_debate_state"] = {"judge_decision": final_decision}
    # `validate_ticker` has already applied the same safe-component policy used
    # by the legacy report path, so this join cannot escape results_dir.
    report_dir = Path(config["results_dir"]) / "reports" / f"{ticker}_{trade_date}"
    report_path = write_report_tree(report_state, ticker, report_dir)

    reflection_path = None
    if reflection:
        # Reflection remains an explicit user/Claude artifact.  It is returned
        # for the next settlement step rather than being treated as an outcome.
        reflection_path = str(report_dir / "reflection.md")
        Path(reflection_path).write_text(str(reflection).strip() + "\n", encoding="utf-8")
    return {
        "recorded": True,
        "ticker": ticker,
        "trade_date": trade_date,
        "decision": normalized,
        "report_path": str(report_path),
        "memory_path": str(config.get("memory_log_path", "")),
        "reflection_path": reflection_path,
    }


def get_outcome(ticker: str, trade_date: str) -> dict[str, Any]:
    """Return a previously recorded decision/outcome without model calls."""
    ticker = validate_ticker(ticker)
    trade_date = validate_trade_date(trade_date)
    from tradingagents.agents.utils.memory import TradingMemoryLog

    entries = TradingMemoryLog(_get_config()).load_entries()
    matches = [e for e in entries if e.get("ticker") == ticker and e.get("date") == trade_date]
    return {"ticker": ticker, "trade_date": trade_date, "found": bool(matches), "entries": jsonable(matches)}


def score_decision_log(ticker: str = "") -> dict[str, Any]:
    """Aggregate settled decisions without running another model call."""
    if ticker:
        ticker = validate_ticker(ticker)
    from tradingagents.agents.utils.memory import TradingMemoryLog

    entries = TradingMemoryLog(_get_config()).load_entries()
    if ticker:
        entries = [entry for entry in entries if entry.get("ticker") == ticker]
    resolved = [entry for entry in entries if not entry.get("pending") and entry.get("alpha")]
    pending = [entry for entry in entries if entry.get("pending")]
    unscored = [entry for entry in entries if entry.get("rating") == "REVIEW"]
    direction = {"Buy": 1, "Overweight": 1, "Hold": 0, "Underweight": -1, "Sell": -1}
    by_rating: dict[str, dict[str, Any]] = {}
    for rating in dict.fromkeys(entry.get("rating") for entry in resolved):
        if not rating:
            continue
        alphas = []
        for entry in resolved:
            if entry.get("rating") != rating:
                continue
            try:
                alphas.append(float(str(entry.get("alpha", "")).rstrip("%")) / 100)
            except ValueError:
                continue
        if not alphas:
            continue
        sign = direction.get(rating, 0)
        by_rating[rating] = {
            "count": len(alphas),
            "hit_rate": (sum(alpha * sign > 0 for alpha in alphas) / len(alphas)) if sign else None,
            "mean_alpha": sum(alphas) / len(alphas),
        }
    return {
        "ticker": ticker or None,
        "resolved": len(resolved),
        "pending": len(pending),
        "unscored": len(unscored),
        "by_rating": by_rating,
    }
