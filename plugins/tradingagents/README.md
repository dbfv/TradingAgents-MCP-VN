# TradingAgents Claude Code plugin

This plugin connects Claude Code to TradingAgents through a local stdio MCP
server. Claude Code keeps the model/provider session; the Python server only
handles configured market-data vendors, deterministic validation, memory, and
reports.

## Local development

From the repository root, install the package and dependencies:

```powershell
python -m pip install -e .
```

The package pins the MCP SDK to the v1 API used by this server entrypoint.

Load the plugin for a session:

```powershell
claude --plugin-dir .\plugins\tradingagents
```

Then invoke:

```text
/tradingagents:analyze NVDA
```

Approve the project MCP server when Claude Code asks. Use `/mcp` to confirm the
`tradingagents` server is connected. Configure only the data keys needed by
your selected vendors, such as `FRED_API_KEY` or `ALPHA_VANTAGE_API_KEY`.
No Anthropic/OpenAI LLM key is read by MCP mode.
