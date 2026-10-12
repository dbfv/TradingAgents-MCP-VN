"""Claude Code MCP integration for TradingAgents.

The MCP package deliberately keeps model orchestration outside Python.  Claude
Code calls these tools using its own authenticated provider session; this
package only exposes deterministic data, validation, memory, and reporting
operations.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"

