"""FastMCP entrypoint for Claude Code."""

from __future__ import annotations

from . import __version__
from . import services


def create_server():
    """Create the server lazily so core contracts remain importable offline."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in install smoke tests
        raise RuntimeError(
            "The MCP SDK is not installed. Install TradingAgents with its base "
            "dependencies (or `pip install mcp`) before starting the server."
        ) from exc

    app = FastMCP("TradingAgents")
    app.tool(name="health")(services.health)
    app.tool(name="get_analysis_briefing")(services.get_analysis_briefing)
    app.tool(name="validate_portfolio")(services.validate_portfolio)
    app.tool(name="get_prior_lessons")(services.get_prior_lessons)
    app.tool(name="get_outcome")(services.get_outcome)
    app.tool(name="score_decision_log")(services.score_decision_log)
    app.tool(name="validate_and_record_decision")(services.validate_and_record_decision)
    return app


def main() -> None:
    """Run the stdio server used by the Claude Code project config."""
    create_server().run(transport="stdio")


__all__ = ["create_server", "main", "__version__"]
