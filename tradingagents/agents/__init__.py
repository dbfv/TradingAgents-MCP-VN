"""Agent factory exports with lazy imports.

The standalone LangGraph runner can still import factories from
``tradingagents.agents`` exactly as before. Lazy exports matter for the MCP
server: reading a decision log must not eagerly load every LangChain agent or
require an LLM SDK/provider credential.
"""

from __future__ import annotations

from importlib import import_module


_LAZY_EXPORTS = {
    "AgentState": ("tradingagents.agents.utils.agent_states", "AgentState"),
    "InvestDebateState": ("tradingagents.agents.utils.agent_states", "InvestDebateState"),
    "RiskDebateState": ("tradingagents.agents.utils.agent_states", "RiskDebateState"),
    "create_msg_delete": ("tradingagents.agents.utils.agent_utils", "create_msg_delete"),
    "create_bear_researcher": ("tradingagents.agents.researchers.bear_researcher", "create_bear_researcher"),
    "create_bull_researcher": ("tradingagents.agents.researchers.bull_researcher", "create_bull_researcher"),
    "create_research_manager": ("tradingagents.agents.managers.research_manager", "create_research_manager"),
    "create_fundamentals_analyst": ("tradingagents.agents.analysts.fundamentals_analyst", "create_fundamentals_analyst"),
    "create_market_analyst": ("tradingagents.agents.analysts.market_analyst", "create_market_analyst"),
    "create_neutral_debator": ("tradingagents.agents.risk_mgmt.neutral_debator", "create_neutral_debator"),
    "create_news_analyst": ("tradingagents.agents.analysts.news_analyst", "create_news_analyst"),
    "create_aggressive_debator": ("tradingagents.agents.risk_mgmt.aggressive_debator", "create_aggressive_debator"),
    "create_portfolio_manager": ("tradingagents.agents.managers.portfolio_manager", "create_portfolio_manager"),
    "create_conservative_debator": ("tradingagents.agents.risk_mgmt.conservative_debator", "create_conservative_debator"),
    "create_sentiment_analyst": ("tradingagents.agents.analysts.sentiment_analyst", "create_sentiment_analyst"),
    "create_social_media_analyst": ("tradingagents.agents.analysts.sentiment_analyst", "create_social_media_analyst"),
    "create_trader": ("tradingagents.agents.trader.trader", "create_trader"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    """Load an agent export only when a caller actually asks for it."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
