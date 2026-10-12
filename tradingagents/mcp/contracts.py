"""Small, dependency-light contracts shared by the MCP server and services.

These validators intentionally do not import LangChain, LangGraph, or an LLM
provider.  That makes it possible to start and health-check the MCP server in a
process that has no model credentials configured.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any


class ContractError(ValueError):
    """Raised when an MCP input violates a public contract."""


_TICKER_RE = re.compile(r"^[A-Za-z0-9._\-\^=+]+$")
_ANALYSTS = frozenset({"market", "technical", "fundamentals", "news", "social", "all"})
_RATINGS = ("Buy", "Overweight", "Hold", "Underweight", "Sell")


def validate_ticker(ticker: str) -> str:
    """Validate a ticker before it can reach a vendor or filesystem path."""
    if not isinstance(ticker, str) or not ticker.strip():
        raise ContractError("ticker must be a non-empty string")
    value = ticker.strip()
    if len(value) > 32:
        raise ContractError("ticker exceeds 32 characters")
    if not _TICKER_RE.fullmatch(value) or set(value) == {"."}:
        raise ContractError(f"ticker contains unsupported characters: {ticker!r}")
    return value


def validate_trade_date(trade_date: str, *, today: date | None = None) -> str:
    """Return a canonical date and reject future as-of queries."""
    if not isinstance(trade_date, str):
        raise ContractError("trade_date must be YYYY-MM-DD")
    try:
        parsed = datetime.strptime(trade_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ContractError("trade_date must be YYYY-MM-DD") from exc
    if parsed.strftime("%Y-%m-%d") != trade_date:
        raise ContractError("trade_date must be YYYY-MM-DD")
    if parsed > (today or date.today()):
        raise ContractError("trade_date cannot be in the future")
    return trade_date


def validate_analyst(analyst: str) -> str:
    value = str(analyst or "").strip().lower()
    if value not in _ANALYSTS:
        allowed = ", ".join(sorted(_ANALYSTS))
        raise ContractError(f"analyst must be one of: {allowed}")
    return value


def validate_look_back_days(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError("look_back_days must be an integer")
    if value < 1 or value > 3650:
        raise ContractError("look_back_days must be between 1 and 3650")
    return value


def validate_rating(value: str) -> str:
    if value not in _RATINGS:
        raise ContractError(f"rating must be one of: {', '.join(_RATINGS)}")
    return value


def parse_json_object(value: Any, *, field_name: str) -> dict[str, Any]:
    """Accept a JSON object or mapping, never an arbitrary file path."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ContractError(f"{field_name} must be a JSON object") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{field_name} must be a JSON object")
    return value


def jsonable(value: Any) -> Any:
    """Convert common vendor/dataclass values into MCP-safe JSON values."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "to_dict"):
        return jsonable(value.to_dict())
    if hasattr(value, "model_dump"):
        return jsonable(value.model_dump())
    if hasattr(value, "__dataclass_fields__"):
        return jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(item) for item in value]
    return str(value)


@dataclass(frozen=True)
class BriefingRequest:
    ticker: str
    trade_date: str
    analyst: str = "market"
    asset_type: str = "stock"
    look_back_days: int = 30

    @classmethod
    def create(
        cls,
        ticker: str,
        trade_date: str,
        analyst: str = "market",
        asset_type: str = "stock",
        look_back_days: int = 30,
    ) -> "BriefingRequest":
        ticker = validate_ticker(ticker)
        trade_date = validate_trade_date(trade_date)
        analyst = validate_analyst(analyst)
        asset_type = str(asset_type or "stock").strip().lower()
        if asset_type not in {"stock", "crypto"}:
            raise ContractError("asset_type must be 'stock' or 'crypto'")
        return cls(ticker, trade_date, analyst, asset_type, validate_look_back_days(look_back_days))


def normalize_decision(value: Any) -> dict[str, Any]:
    """Validate and normalize the public Portfolio Manager decision shape."""
    decision = parse_json_object(value, field_name="decision")
    rating = validate_rating(decision.get("rating"))
    summary = str(decision.get("executive_summary") or "").strip()
    thesis = str(decision.get("investment_thesis") or "").strip()
    if not summary:
        raise ContractError("decision.executive_summary is required")
    if not thesis:
        raise ContractError("decision.investment_thesis is required")

    price_target = decision.get("price_target")
    if price_target in ("", "none", "None", "N/A", "n/a"):
        price_target = None
    if price_target is not None:
        try:
            price_target = float(price_target)
        except (TypeError, ValueError) as exc:
            raise ContractError("decision.price_target must be numeric or null") from exc
        if price_target <= 0:
            raise ContractError("decision.price_target must be positive")

    horizon = decision.get("time_horizon")
    horizon = str(horizon).strip() if horizon is not None else None
    return {
        "rating": rating,
        "executive_summary": summary,
        "investment_thesis": thesis,
        "price_target": price_target,
        "time_horizon": horizon or None,
    }

